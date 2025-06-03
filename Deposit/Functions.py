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


class IdentityVerificationResult(BaseModel):
    name_similarity: int
    name_match: bool
    id_match: bool
    dob_match: bool
    all_fields_match: bool
    notes: Optional[str]


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
    all_fields_verified: bool
    explanation: str


class BankStatementAIResult(BaseModel):
    name_match: bool
    address_match: bool
    iban_match: bool
    bic_match: bool
    all_fields_verified: bool
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
        "notes": []
    }

    if not name_match:
        result["notes"].append(f"Name mismatch: '{fullName}' vs '{MRZName}'")
    if not id_match:
        result["notes"].append(f"ID mismatch: '{personalId}' vs '{MRZId}'")
    if not dob_match:
        result["notes"].append(
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
            "salary_bracket_match": true/false,
            "all_fields_verified": true/false,
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
        "all_fields_verified": true or false,
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

        db = firestore.client()
        db.collection("deposits").document(id).set(data)

        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()

        if user_doc.exists:
            try:
                # Parse deposit amount and determine tier
                deposit_amount = float(data.get("amount", 0))

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

            return "200"
        else:
            return {"error": "Failed to save deposit"}, 500

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def VerifyDeposit(deposit):
    deposit = deposit.get_json()

    # Personal ID
    # PersonalIDFile = deposit['uploadedDocuments']['personalId']
    # MRZData = GetMRZData(PersonalIDFile)
    # MRZData = json.loads(MRZData)
    # if MRZData["status"] == "SUCCESS":
    #     result = verify_identity(deposit,MRZData)

    # if MRZData["status"] == "FAILURE":
    #     result = verify_identity_with_AI(deposit, MRZData)


    

    fullName = deposit.get('fullName', '').strip()
    pincode = deposit.get('pincode')
    city = deposit.get('city')
    address = deposit.get('address')
    ibanCode = deposit.get('ibanCode')
    bicId = deposit.get('bicId')
    fulladress = address+city+pincode


    # Income Proof 
    # IncomeProof = deposit['uploadedDocuments']['IncomeProof']
    # IncomeProofMarkdown = extract_markdown(IncomeProof)
    # result = verify_payslip_with_AI(IncomeProofMarkdown, fullName, annualIncome)


    # Bank Statement 
    
    bankStatement = deposit['uploadedDocuments']['bankStatement']
    bankStatementMarkdown = extract_markdown(bankStatement)
    result = verify_bank_statement_with_AI(bankStatementMarkdown,fullName,fulladress,ibanCode,bicId)




    return result
