import os
import pandas as pd
from django.conf import settings
from api.models import Customer, Loan
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task()
def ingest_customer_data():
    try:
        file_path = os.path.join(settings.BASE_DIR, "customer_data.xlsx")
        customer_data = pd.read_excel(file_path)

        for _, row in customer_data.iterrows():
            customer_id = row["Customer ID"]

            # Check if the customer already exists
            customer, created = Customer.objects.update_or_create(
                customer_id=customer_id,
                defaults={
                    "first_name": row["First Name"],
                    "last_name": row["Last Name"],
                    "age": row["Age"],
                    "phone_number": row["Phone Number"],
                    "monthly_income": row["Monthly Salary"],
                    "approved_limit": row["Approved Limit"],
                },
            )
            if created:
                logger.info(f"New Customer {customer} created.")
    
    except FileNotFoundError as e:
        logger.error(f"Customer data file not found: {e}")
    except Exception as e:
        logger.error(f"Error during customer data ingestion: {e}")


@shared_task()
def ingest_loan_data():
    try:
        file_path = os.path.join(settings.BASE_DIR, "loan_data.xlsx")
        df = pd.read_excel(file_path)
        df["Loan Approved"] = True

        for _, row in df.iterrows():
            loan_id = row["Loan ID"]

            try:
                customer = Customer.objects.get(customer_id=row["Customer ID"])
            except Customer.DoesNotExist:
                logger.warning(f'Customer with ID {row["Customer ID"]} does not exist. Skipping loan.')
                continue

            # Create or update the loan
            Loan.objects.update_or_create(
                loan_id=loan_id,
                defaults={
                    "customer": customer,
                    "loan_amount": row["Loan Amount"],
                    "tenure": row["Tenure"],
                    "interest_rate": row["Interest Rate"],
                    "monthly_repayment": row["Monthly payment"],
                    "emis_paid_on_time": row["EMIs paid on Time"],
                    "date_of_approval": row["Date of Approval"],
                    "end_date": row["End Date"],
                    "loan_approved": row["Loan Approved"],
                },
            )

    except FileNotFoundError as e:
        logger.error(f"Customer data file not found: {e}")
    except Exception as e:
        logger.error(f"Error during loan data ingestion: {e}")