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


def sell_asset(user_id, sell_data):
    try:
        db = firestore.client()
        mfid = sell_data.get('isin')
        amount_to_redeem = float(sell_data.get('shares', 0))
        if not mfid or amount_to_redeem <= 0:
            return {'error': 'Invalid sell data'}, 400

        # Get user's assets
        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        if not assets_doc.exists:
            return {'error': 'No assets found for user'}, 404
        assets_data = assets_doc.to_dict()
        assets_list = assets_data.get('assets', [])
        asset_found = False
        for i, asset in enumerate(assets_list):
            if asset.get('isin') == mfid:
                current_shares = float(asset.get('shares', 0))
                name = asset.get('name')
                # Get latest NAV
                funds_ref = db.collection('funds')
                fund_doc = funds_ref.document(mfid).get()
                nav = float(fund_doc.to_dict().get('latestnav', asset.get('nav', 0))) if fund_doc.exists else float(asset.get('nav', 0))
                if nav <= 0:
                    return {'error': 'Invalid NAV value'}, 400
                shares_to_sell = amount_to_redeem / nav
                if shares_to_sell > current_shares:
                    return {'error': 'Not enough shares to sell'}, 400
                value = shares_to_sell * nav  # This should be close to amount_to_redeem
                # Remove shares
                remaining_shares = current_shares - shares_to_sell
                if remaining_shares <= 0.00001:  # Floating point tolerance
                    assets_list.pop(i)
                else:
                    asset['shares'] = remaining_shares
                    assets_list[i] = asset
                asset_found = True
                break
        if not asset_found:
            return {'error': 'Asset not found'}, 404
        # Update assets
        assets_ref.set({'assets': assets_list}, merge=True)
        # Add value to deposit
        deposit_ref = db.collection('deposits').document(user_id)
        deposit_doc = deposit_ref.get()
        if not deposit_doc.exists:
            return {'error': 'Deposit record not found'}, 404
        deposit_data = deposit_doc.to_dict()
        available_funds = float(deposit_data.get('availableFunds', 0)) + value
        deposit_ref.update({'availableFunds': available_funds, 'editedAt': datetime.now(timezone.utc)})
        # Log transaction
        log_ref = db.collection('transactions').document()
        log_ref.set({
            'user_id': user_id,
            'mfid': mfid,
            'shares_sold': shares_to_sell,
            'nav': nav,
            'value': value,
            'timestamp': datetime.now(timezone.utc),
            'type': 'sell'
        })

        log_data = {
            'userId': user_id,
            'action': 'Sell',
            'date': datetime.now(timezone.utc),
            'type': 'Redeam',    
            'description': name,
            'amount': amount_to_redeem
        }

        db.collection('logs').add(log_data)


        return {
            'message': 'Asset sold successfully',
            'value': value,
            'shares_sold': shares_to_sell,
            'shares_remaining': remaining_shares if asset_found else 0,
            'availableFunds': available_funds
        }, 200
    except Exception as e:
        print(f"Error selling asset for {user_id}: {e}")
        return {'error': str(e)}, 500

def get_single_asset_info(user_id, data):
    try:
        isin = data.get('isin')
        if not isin:
            return {'error': 'ISIN is required'}, 400
        db = firestore.client()
        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        if not assets_doc.exists:
            return {'error': 'No assets found for user'}, 404
        assets_list = assets_doc.to_dict().get('assets', [])
        asset = next((a for a in assets_list if a.get('isin') == isin), None)
        if not asset:
             return {
                'isin': isin,
                'fund_name': '',
                'fund_category': '',
                'fund_type': '',
                'amount_invested': 0,
                'current_nav': 0,
                'total_returns': 0,
                'total_units': 0
            },200
        # Get fund info
        funds_ref = db.collection('funds')
        fund_doc = funds_ref.document(isin).get()
        fund_info = fund_doc.to_dict() if fund_doc.exists else {}
        fund_name = fund_info.get('name', '')
        fund_category = fund_info.get('category', '')
        fund_type = fund_info.get('type', '')
        current_nav = float(fund_info.get('latestnav', asset.get('nav', 0)))
        shares = float(asset.get('shares', 0))
        amount_invested = shares * float(asset.get('old_nav', asset.get('nav', 0)))
        total_returns = (current_nav - float(asset.get('old_nav', asset.get('nav', 0)))) * shares
        result = {
            'isin': isin,
            'fund_name': fund_name,
            'fund_category': fund_category,
            'fund_type': fund_type,
            'amount_invested': amount_invested,
            'current_nav': current_nav,
            'total_returns': total_returns,
            'total_units': shares
        }
        return result, 200
    except Exception as e:
        print(f"Error retrieving single asset info for {user_id}: {e}")
        return {'error': str(e)}, 500

def get_quick_stats(user_id):
    try:
        db = firestore.client()
        assets_ref = db.collection('assets').document(user_id)
        assets_doc = assets_ref.get()
        assets = []
        if assets_doc.exists:
            assets = assets_doc.to_dict().get('assets', [])
        total_invested = 0
        best_performer = None
        best_performance = float('-inf')
        num_funds = len(assets)
        now = datetime.now(timezone.utc)
        oldest_date = now
        for asset in assets:
            shares = float(asset.get('shares', 0))
            old_nav = float(asset.get('old_nav', asset.get('nav', 0)))
            invested = shares * old_nav
            total_invested += invested
            isin = asset.get('isin')
            # Get fund info
            funds_ref = db.collection('funds')
            fund_doc = funds_ref.document(isin).get()
            fund_info = fund_doc.to_dict() if fund_doc.exists else {}
            fund_name = fund_info.get('name', isin)
            current_nav = float(fund_info.get('latestnav', asset.get('nav', 0)))
            perf = ((current_nav - old_nav) / old_nav * 100) if old_nav > 0 else 0
            if perf > best_performance:
                best_performance = perf
                best_performer = f"{fund_name} (+{round(perf, 1)}%)"
            # Portfolio age
            pd = asset.get('purchaseDate')
            if pd:
                if isinstance(pd, str):
                    try:
                        pd_dt = datetime.fromisoformat(pd)
                    except Exception:
                        continue
                else:
                    pd_dt = pd
                if pd_dt < oldest_date:
                    oldest_date = pd_dt
        # Portfolio age calculation
        age_years = now.year - oldest_date.year
        age_months = now.month - oldest_date.month
        if age_months < 0:
            age_years -= 1
            age_months += 12
        portfolio_age = f"{age_years} years {age_months} months" if num_funds > 0 else "0 months"
        stats = {
            'total_invested': round(total_invested, 2),
            'num_funds': num_funds,
            'best_performer': best_performer or '',
            'portfolio_age': portfolio_age
        }
        return stats, 200
    except Exception as e:
        print(f"Error getting quick stats for {user_id}: {e}")
        return {'error': str(e)}, 500

def get_managed_users_assets(manager_id):
    try:
        db = firestore.client()
        # Get manager's managed users
        manager_ref = db.collection('users').document(manager_id)
        manager_doc = manager_ref.get()
        if not manager_doc.exists:
            return {'error': 'Manager not found'}, 404
        manager_data = manager_doc.to_dict()
        managed_users = manager_data.get('managedUsers', [])
        result = []
        for user_id in managed_users:
            # Get deposit info
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
            user_assets = []
            for asset in assets:
                isin = asset.get('isin')
                name = asset.get('name')
                shares = float(asset.get('shares', 0))
                nav = float(asset.get('nav', 0))
                amount_invested = shares * float(asset.get('old_nav', nav))
                user_assets.append({
                    'name': name,
                    'isin': isin,
                    'shares': round(shares, 2),
                    'amount_invested': round(amount_invested, 2)
                })
            result.append({
                'user_id': user_id,
                'available_funds': round(available_funds, 2),
                'assets': user_assets
            })
        return result, 200
    except Exception as e:
        print(f"Error getting managed users assets for {manager_id}: {e}")
        return {'error': str(e)}, 500

def get_manager_stats(manager_id):
    try:
        db = firestore.client()
        # Get manager's managed users
        manager_ref = db.collection('users').document(manager_id)
        manager_doc = manager_ref.get()
        if not manager_doc.exists:
            return {'error': 'Manager not found'}, 404
        manager_data = manager_doc.to_dict()
        managed_users = manager_data.get('managedUsers', [])
        total_clients = len(managed_users)
        total_aum = 0
        total_perf = 0
        perf_count = 0
        active_orders = 0
        for user_id in managed_users:
            # Get assets
            assets_ref = db.collection('assets').document(user_id)
            assets_doc = assets_ref.get()
            assets = []
            if assets_doc.exists:
                assets = assets_doc.to_dict().get('assets', [])
            user_aum = 0
            user_perf = 0
            user_perf_count = 0
            for asset in assets:
                shares = float(asset.get('shares', 0))
                nav = float(asset.get('nav', 0))
                old_nav = float(asset.get('old_nav', nav))
                fund_isin = asset.get('isin')
                # Get latest NAV
                funds_ref = db.collection('funds')
                fund_doc = funds_ref.document(fund_isin).get()
                current_nav = float(fund_doc.to_dict().get('latestnav', nav)) if fund_doc.exists else nav
                user_aum += shares * current_nav
                if old_nav > 0:
                    user_perf += ((current_nav - old_nav) / old_nav * 100)
                    user_perf_count += 1
            total_aum += user_aum
            if user_perf_count > 0:
                total_perf += (user_perf / user_perf_count)
                perf_count += 1
            # Count active orders (buy/sell logs)
            logs_ref = db.collection('logs')
            logs = logs_ref.where('userId', '==', user_id).stream()
            for log in logs:
                if log.to_dict().get('action') in ['Buy', 'Sell']:
                    active_orders += 1
        avg_perf = (total_perf / perf_count) if perf_count > 0 else 0
        stats = {
            'total_clients': total_clients,
            'total_aum': round(total_aum, 2),
            'avg_performance': round(avg_perf, 2),
            'active_orders': active_orders
        }
        return stats, 200
    except Exception as e:
        print(f"Error getting manager stats for {manager_id}: {e}")
        return {'error': str(e)}, 500
