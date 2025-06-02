from firebase_admin import firestore
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone
from Helpers.MRZScane import GetMRZData
from Helpers.MinerU import extract_markdown


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
    PersonalIDFile = deposit['uploadedDocuments'].personalId
    MRZData = GetMRZData(PersonalIDFile)
    # TODO process data and compare
    IncomeProof = deposit['uploadedDocuments'].IncomeProof
    IncomeProofMarkdown = extract_markdown(IncomeProof)
    # TODO Call groq and cross verify the data

