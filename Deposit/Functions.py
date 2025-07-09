from firebase_admin import firestore
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone
from Helpers.MRZScane import GetMRZData
from Helpers.MinerU import extract_markdown
from fuzzywuzzy import fuzz
from Helpers.NormalizeDate import normalize_date
from pydantic import BaseModel
from typing import Optional, Dict, Any
from instructor import from_groq, Mode
from groq import Groq
import json
import threading
import random

class IdentityVerificationResult(BaseModel):
    name_similarity: int
    name_match: bool
    id_match: bool
    dob_match: bool
    all_fields_match: bool
    explanation: Optional[str]


class IdentityVerificationAIResult(BaseModel):
    name_similarity: int
    name_match: bool
    id_match: bool
    dob_match: bool
    all_fields_match: bool
    explanation: str


class AIResult(BaseModel):
    name_match: bool
    date_valid: bool
    net_pay_detected: bool
    salary_bracket: str
    salary_bracket_match: bool
    all_fields_match: bool
    explanation: str


class BankStatementAIResult(BaseModel):
    name_match: bool
    address_match: bool
    iban_match: bool
    bic_match: bool
    all_fields_match: bool
    explanation: str


def verify_identity(deposit: Dict[str, str], MRZData: Dict[str, str]) -> Dict[str, Any]:
    fullName = deposit.get('fullName', '').strip()
    personalId = deposit.get('personalId', '').strip()
    dateOfBirth_raw = deposit.get('dateOfBirth', '').strip()

    MRZName = f"{MRZData.get('surname', '').strip()} {MRZData.get('given_name', '').strip()}"
    MRZId = MRZData.get('document_number', '').strip()
    MRZdateOfBirth_raw = MRZData.get('birth_date', '').strip()

    # Normalize dates
    dateOfBirth = normalize_date(dateOfBirth_raw)
    MRZdateOfBirth = normalize_date(MRZdateOfBirth_raw)

    # Fuzzy name matching
    name_similarity = fuzz.token_sort_ratio(fullName, MRZName)
    name_match = name_similarity >= 85
    id_match = personalId == MRZId
    dob_match = dateOfBirth == MRZdateOfBirth
    all_fields_match = name_match and id_match and dob_match

    result = {
        "name_similarity": name_similarity,
        "name_match": name_match,
        "id_match": id_match,
        "dob_match": dob_match,
        "all_fields_match": all_fields_match,
        "explanation": []
    }

    if not name_match:
        result["explanation"].append(f"Name mismatch: '{fullName}' vs '{MRZName}'")
    if not id_match:
        result["explanation"].append(f"ID mismatch: '{personalId}' vs '{MRZId}'")
    if not dob_match:
        result["explanation"].append(
            f"Date of birth mismatch: '{dateOfBirth_raw}' vs '{MRZdateOfBirth_raw}'")

    return result


def verify_identity_with_AI(deposit: Dict[str, str], MRZData: Dict[str, str]) -> Dict[str, Any]:
    # Prepare input
    fullName = deposit.get('fullName', '').strip()
    personalId = deposit.get('personalId', '').strip()
    dateOfBirth_raw = deposit.get('dateOfBirth', '').strip()

    MRZName = f"{MRZData.get('surname', '').strip()} {MRZData.get('given_name', '').strip()}"
    MRZId = MRZData.get('document_number', '').strip()
    MRZdateOfBirth_raw = MRZData.get('birth_date', '').strip()

    dateOfBirth = normalize_date(dateOfBirth_raw)
    MRZdateOfBirth = normalize_date(MRZdateOfBirth_raw)
    dob_match = dateOfBirth == MRZdateOfBirth

    name_similarity = fuzz.token_sort_ratio(fullName, MRZName)
    name_match = name_similarity >= 85
    id_match = personalId == MRZId

    # # Prepare prompt
    prompt = f"""
        You are verifying user identity between a deposit form and MRZ data (machine-readable zone on a passport or ID).

        Here are the fields:

        Deposit:
        - Full Name: {fullName}
        - Personal ID: {personalId}
        - Date of Birth: {dateOfBirth}

        MRZ:
        - Full Name: {MRZName}
        - Personal ID: {MRZId}
        - Date of Birth: {MRZdateOfBirth}

        Evaluation metrics (for reference only, do not base your decision solely on these):
        - Name similarity score (fuzzy): {name_similarity}
        - Name match (threshold ≥ 85): {name_match}
        - ID match: {id_match}
        - DOB match: {dob_match}

        Your job:
        - Determine if the names match (accounting for formatting differences or partial matches).
        - Check whether personal IDs match.
        - Check if the date of birth is the same.
        - Compute a name similarity score (0–100).
        - Based on these, determine if all fields match.
        - Provide a clear explanation of your conclusion.

        Respond by calling the function `IdentityVerificationAIResult` with the following fields:
        {{
            "name_similarity": int,
            "name_match": true/false,
            "id_match": true/false,
            "dob_match": true/false,
            "all_fields_match": true/false,
            "explanation": string
        }}
    """

    # Connect to Groq
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    client = from_groq(client, mode=Mode.TOOLS)

    # AI call
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-70b-8192",
        response_model=IdentityVerificationAIResult
    )

    # Return structured response
    return response.model_dump()


def verify_payslip_with_AI(payslip_text: str, expected_name: str, salary_key: str) -> Dict[str, Any]:

    salary_brackets = {
        "0-25k": "< €25,000 Euros",
        "25k-40k": "€25,000 - €40,000 Euros",
        "40k-60k": "€40,000 - €60,000 Euros",
        "60k-80k": "€60,000 - €80,000 Euros",
        "80k-120k": "€80,000 - €120,000 Euros",
        "120k+": "> €120,000 Euros"
    }

    if salary_key not in salary_brackets:
        raise ValueError(f"Invalid salary_key: {salary_key}")

    expected_bracket = salary_brackets[salary_key]

    prompt = f"""
        You are verifying a payslip. Here is the raw payslip text:

        --- PAYSPLIP START ---
        {payslip_text}
        --- PAYSPLIP END ---

        Verification tasks:
        - Expected employee name: **{expected_name}**
        - Expected salary bracket: **{expected_bracket}**
        - The date of joining should be **at least 1 year ago**
        - If net pay is mentioned (monthly), calculate the **annual salary** and verify if it fits the expected salary bracket.

        Respond by calling the function `AIResult` with the following fields:
        {{
            "name_match": true/false,
            "date_valid": true/false,
            "net_pay_detected": true/false,
            "salary_bracket": "string",
            "salary_bracket_match": true/false,ss
            "all_fields_match": true/false,
            "explanation": "string"
        }}
    """
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    client = from_groq(client, mode=Mode.TOOLS)

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        response_model=AIResult,
    )

    return response.model_dump()


def verify_bank_statement_with_AI(
    statement_text: str,
    expected_name: str,
    expected_address: str,
    expected_iban: str,
    expected_bic: str,
) -> Dict[str, Any]:

    prompt = f"""   
        You are verifying a scanned or OCR-read bank statement. Here is the raw document text:

        --- BANK STATEMENT START ---
        {statement_text}
        --- BANK STATEMENT END ---

        Verification details:
        - Expected account holder name: **{expected_name}**
        - Expected address: **{expected_address}**
        - Expected IBAN: **{expected_iban}**
        - Expected BIC: **{expected_bic}**

        Instructions:
        - You must check if the name, address, IBAN, and BIC are reasonably present in the document.
        - Some values (especially address or name) may be scattered or have different ordering (e.g., "Fontenay 96 95202" can appear as "Postcode 95202 Fontenay").
        - Minor formatting variations are acceptable.
        - Consider fuzzy or partial matches as valid if they are strongly indicative.

        Respond by calling the function `BankStatementAIResult` with the following fields:
        {{
        "name_match": true or false,
        "address_match": true or false,
        "iban_match": true or false,
        "bic_match": true or false,
        "all_fields_match": true or false,
        "explanation": "A concise explanation of what matched and what didn't."
        }}
    """

    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    client = from_groq(client, mode=Mode.TOOLS)

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        response_model=BankStatementAIResult,
    )

    return response.model_dump()


def VerifyDeposit(deposit):
    # Personal ID   
    PersonalIDFile = deposit['uploadedDocuments']['personalId']
    MRZData = GetMRZData(PersonalIDFile)
    MRZData = json.loads(MRZData)
    if MRZData["status"] == "SUCCESS":
        result = verify_identity(deposit,MRZData)

    if MRZData["status"] == "FAILURE":
        result = verify_identity_with_AI(deposit, MRZData)


    if result['all_fields_match'] == False:
        return False,result['explanation']

    print("Passed PERSONAL ID")

    fullName = deposit.get('fullName', '').strip()
    pincode = deposit.get('pincode')
    annualIncome = deposit.get('annualIncome')
    city = deposit.get('city')
    address = deposit.get('address')
    ibanCode = deposit.get('ibanCode')
    bicId = deposit.get('bicId')
    fulladress = address+city+pincode


    # Income Proof 
    IncomeProof = deposit['uploadedDocuments']['incomeProof']
    IncomeProofMarkdown = extract_markdown(IncomeProof)
    result = verify_payslip_with_AI(IncomeProofMarkdown, fullName, annualIncome)

    if result['all_fields_match'] == False:
        return False,result['explanation']

    print("Passed INCOME PROOF")

    # Bank Statement 
    bankStatement = deposit['uploadedDocuments']['bankStatement']
    bankStatementMarkdown = extract_markdown(bankStatement)
    result = verify_bank_statement_with_AI(bankStatementMarkdown,fullName,fulladress,ibanCode,bicId)

    if result['all_fields_match'] == False:
        return False,result['explanation']

    print("Passed BANK STATEMENT")

    return True,result['explanation']


def SaveDeposit(id, request):
    try:
        file_keys = ['personalid', 'bankstatemet',
                     'AddressProof', 'IncomeProof']
        saved_files = {}

        for key in file_keys:
            if key not in request.files:
                return {"error": f"Missing file: {key}"}, 400

            file = request.files[key]

            if file.filename == '':
                return {"error": f"No selected file for {key}"}, 400

            if file:
                filename = secure_filename(file.filename)
                random_filename = f"{os.urandom(16).hex()}_{filename}"

                user_dir = os.path.join('Files', id)
                os.makedirs(user_dir, exist_ok=True)

                save_path = os.path.join(user_dir, f"{key}_{random_filename}")
                file.save(save_path)

                saved_files[key] = os.path.relpath(save_path, start='Files')

        # Extract form data
        data = request.form.to_dict()

        # Add saved file names to data
        data['uploadedDocuments'] = {
            "personalId": saved_files.get("personalid", ""),
            "addressProof": saved_files.get("AddressProof", ""),
            "bankStatement": saved_files.get("bankstatemet", ""),
            "incomeProof": saved_files.get("IncomeProof", "")
        }
        data['status'] = 'pending'

        now = datetime.now(timezone.utc)
        data['createdAt'] = now
        data['editedAt'] = now


        deposit_amount = float(data.get("amount", 0))
        data['availableFunds'] = deposit_amount

        db = firestore.client()
        db.collection("deposits").document(id).set(data)

        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()

        if user_doc.exists:
            try:
                # Parse deposit amount and determine tier
                if deposit_amount >= 25000:
                    tier = "Platinum"
                elif deposit_amount >= 5000:
                    tier = "Gold"
                elif deposit_amount >= 1000:
                    tier = "Silver"
                else:
                    tier = None

                if tier:
                    user_ref.update({"depositTier": tier})
            except ValueError:
                print("Invalid deposit amount, skipping tier update.")


            # Handle quiz creation in background
            def async_verify():
                result = VerifyDeposit(data)
                status = "Accepted" if result[0] == True else "Rejected"
                db.collection("deposits").document(id).update({
                    "status": status,
                    "editedAt": datetime.now(timezone.utc)
                })
                
                managers = db.collection("users").where("role", "==", "manager").stream()
                manager_ids = [mgr.id for mgr in managers]
                if manager_ids:
                    selected_manager_id = random.choice(manager_ids)
                    user_ref.update({"managerId": selected_manager_id})

                    manager_ref = db.collection("users").document(selected_manager_id)
                    manager_doc = manager_ref.get()
                    if manager_doc.exists:
                        managed_users = manager_doc.to_dict().get("managedUsers", [])
                        if id not in managed_users:
                            managed_users.append(id)
                            manager_ref.update({"managedUsers": managed_users})


                    chat_data = {
                        "iduser1": id,
                        "iduser2": selected_manager_id,
                        "createdAt": datetime.now(timezone.utc),
                        "chats": []
                    }
                    chat_ref = db.collection("chats").document()
                    chat_ref.set(chat_data)
                    


            threading.Thread(target=async_verify).start()   

            return "200"
        else:
            return {"error": "Failed to save deposit"}, 500
        


    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def get_available_funds(user_id:str):
    try:
        db = firestore.client()
        doc_ref = db.collection("deposits").document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            print(data)
            return data.get("availableFunds")
        else:
            return None
    except Exception as e:
        print(f"Error retrieving available funds for {user_id}: {e}")
        return None


def add_funds(user_id, request):
    try:
        db = firestore.client()
        doc_ref = db.collection("deposits").document(user_id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"error": "Deposit record not found"}, 404

        if request.is_json:
            try:
                req_data = request.get_json(force=True, silent=True)
                if isinstance(req_data, dict):
                    amount = float(req_data.get("amount", 0))
                else:
                    amount = float(req_data)
            except Exception:
                amount = 0
        else:
            amount = float(request.form.get("amount", 0))

        if amount <= 0:
            return {"error": "Amount must be positive"}, 400

        data = doc.to_dict()
        current_funds = float(data.get("availableFunds", 0))
        new_funds = current_funds + amount

        log_data = {
            'userId': user_id,
            'action': 'Deposit',
            'date': datetime.now(timezone.utc),    
            'description': "Bank",
            'amount': amount
        }

        db.collection('logs').add(log_data)

        doc_ref.update({
            "availableFunds": new_funds,
            "editedAt": datetime.now(timezone.utc)
        })
        return {"availableFunds": new_funds}
    except Exception as e:
        print(f"Error adding funds for {user_id}: {e}")
        return {"error": str(e)}, 500


def buy_asset(user_id, asset_data):
    try:
        db = firestore.client()
        isin = asset_data.get('isin')
        amount_invested = float(asset_data.get('amount_invested', 0))
        nav_price = float(asset_data.get('nav_price', 0))
        name = asset_data.get('name')
        purchase_date = datetime.now(timezone.utc)
        if not isin or nav_price <= 0 or amount_invested <= 0:
            return {'error': 'Invalid asset data'}, 400
        # Retrieve and update availableFunds
        deposit_ref = db.collection('deposits').document(user_id)
        deposit_doc = deposit_ref.get()
        if not deposit_doc.exists:
            return {'error': 'Deposit record not found'}, 404
        deposit_data = deposit_doc.to_dict()
        current_funds = float(deposit_data.get('availableFunds', 0))
        if amount_invested > current_funds:
            return {'error': 'Insufficient available funds'}, 400
        new_funds = current_funds - amount_invested
        deposit_ref.update({
            'availableFunds': new_funds,
            'editedAt': datetime.now(timezone.utc)
        })
        num_shares = amount_invested / nav_price
        asset_doc = {
            'isin': isin,
            'name': name,
            'nav': nav_price,
            'shares': num_shares,
            'purchaseDate': purchase_date
        }

        log_data = {
            'userId': user_id,
            'action': 'Buy',
            'date': datetime.now(timezone.utc),
            'type': 'SIP',    
            'description': name,
            'amount': amount_invested
        }

        db.collection('logs').add(log_data)
       


        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        merged = False
        if assets_doc.exists:
            assets_data = assets_doc.to_dict()
            assets_list = assets_data.get('assets', [])
            for i, existing_asset in enumerate(assets_list):
                if existing_asset.get('isin') == isin:
                    total_shares = float(existing_asset.get('shares', 0)) + num_shares
                    assets_list[i] = {
                        'isin': isin,
                        'name': name,
                        'nav': nav_price,
                        'shares': total_shares,
                        'purchaseDate': purchase_date
                    }
                    merged = True
                    break
            if merged:
                assets_ref.set({'assets': assets_list}, merge=True)
                return {'message': 'Asset merged successfully', 'asset': assets_list[i], 'availableFunds': new_funds}, 200
            else:
                assets_ref.set({'assets': firestore.ArrayUnion([asset_doc])}, merge=True)
                return {'message': 'Asset saved successfully', 'asset': asset_doc, 'availableFunds': new_funds}, 200
        else:
            assets_ref.set({'assets': [asset_doc]}, merge=True)
            return {'message': 'Asset saved successfully', 'asset': asset_doc, 'availableFunds': new_funds}, 200
    except Exception as e:
        print(f"Error saving asset for {user_id}: {e}")
        return {'error': str(e)}, 500


def get_assets(user_id):
    try:
        db = firestore.client()
        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        if assets_doc.exists:
            assets_data = assets_doc.to_dict()
            return {'assets': assets_data.get('assets', [])}, 200
        else:
            return {'assets': []}, 200
    except Exception as e:
        print(f"Error retrieving assets for {user_id}: {e}")
        return {'error': str(e)}, 500


def get_portfolio_metrics(user_id):
    try:
        db = firestore.client()
        # Get available funds
        deposit_ref = db.collection('deposits').document(user_id)
        deposit_doc = deposit_ref.get()
        available_funds = 0
        if deposit_doc.exists:
            deposit_data = deposit_doc.to_dict()
            available_funds = float(deposit_data.get('availableFunds', 0))
        # Get assets
        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        assets = []
        if assets_doc.exists:
            assets = assets_doc.to_dict().get('assets', [])
        total_value = 0
        total_gains = 0
        total_invested = 0

        # Fetch latest NAVs for all ISINs in user's assets
        isin_list = [asset.get('isin') for asset in assets if asset.get('isin')]
        latest_navs = {}
        if isin_list:
            funds_ref = db.collection('funds')
            for isin in isin_list:
                fund_doc = funds_ref.document(isin).get()
                if fund_doc.exists:
                    fund_data = fund_doc.to_dict()
                    latest_nav = fund_data.get('latestnav')
                    if latest_nav is not None:
                        latest_navs[isin] = float(latest_nav)

        for asset in assets:
            shares = float(asset.get('shares', 0))
            isin = asset.get('isin')
            # Use latest NAV from funds table if available, else fallback to asset's nav
            nav = latest_navs.get(isin, float(asset.get('nav', 0)))
            old_nav = float(asset.get('old_nav', asset.get('nav', 0)))  # fallback to nav if not present
            total_value += shares * nav
            total_invested += shares * old_nav
            total_gains += (nav - old_nav) * shares

        # This Month: sum of assets purchased this month
        from datetime import datetime
        from_zone = timezone.utc
        now = datetime.now(from_zone)
        this_month = now.month
        this_year = now.year
        month_invested = 0
        for asset in assets:
            pd = asset.get('purchaseDate')
            if pd:
                if isinstance(pd, str):
                    try:
                        pd_dt = datetime.fromisoformat(pd)
                    except Exception:
                        continue
                else:
                    pd_dt = pd
                if pd_dt.month == this_month and pd_dt.year == this_year:
                    isin = asset.get('isin')
                    nav = latest_navs.get(isin, float(asset.get('nav', 0)))
                    month_invested += nav * float(asset.get('shares', 0))
        metrics = {
            'total_portfolio_value': total_value,
            'total_gains': total_value - total_invested,
            'total_gains_percent': ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0,
            'available_funds': available_funds,
            'this_month': month_invested
        }
        return metrics, 200
    except Exception as e:
        print(f"Error getting portfolio metrics for {user_id}: {e}")
        return {'error': str(e)}, 500

def get_assets_with_fund_info(user_id):
    try:
        db = firestore.client()
        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        assets = []
        if assets_doc.exists:
            assets = assets_doc.to_dict().get('assets', [])
        result = []
        funds_ref = db.collection('funds')
        for asset in assets:
            isin = asset.get('isin')
            shares = float(asset.get('shares', 0))
            nav = float(asset.get('nav', 0))
            amount_invested = shares * float(asset.get('old_nav', nav))
            fund_doc = funds_ref.document(isin).get()
            fund_info = fund_doc.to_dict() if fund_doc.exists else {}
            fund_name = fund_info.get('name', '')
            fund_category = fund_info.get('category', '')
            fund_type = fund_info.get('type', '')
            risk = fund_info.get('risk', '')
            current_nav = float(fund_info.get('latestnav', nav))
            total_units = shares
            total_returns = (current_nav - float(asset.get('old_nav', nav))) * shares
            gains = (current_nav * shares) - amount_invested
            gains_percentage = (gains / amount_invested * 100) if amount_invested > 0 else 0
            result.append({
                'isin': isin,
                'fund_name': fund_name,
                'fund_category': fund_category,
                'fund_type': fund_type,
                'risk': risk,
                'amount_invested': round(amount_invested, 2),
                'current_nav': round(current_nav, 2),
                'total_returns': round(total_returns, 2),
                'total_units': round(total_units, 2),
                'gains': round(gains, 2),
                'gains_percentage': round(gains_percentage, 2),
                'todayChange': 1.20,  # If this should be dynamic, update accordingly
            })
        return result, 200
    except Exception as e:
        print(f"Error retrieving assets with fund info for {user_id}: {e}")
        return {'error': str(e)}, 500
