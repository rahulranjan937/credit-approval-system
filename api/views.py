from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    CustomerSerializer,
    CheckEligibilitySerializer,
    LoanSerializer,
    LoanViewSerializer,
)
from django.db.models import Sum, Max
from .models import Customer, Loan
from datetime import date
from dateutil.relativedelta import relativedelta


@api_view(["POST"])
def register_customer_view(request):
    serializer = CustomerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    monthly_salary = serializer.validated_data["monthly_income"]
    approved_limit = round(36 * monthly_salary, -5)

    customer = serializer.save(approved_limit=approved_limit)

    response_data = {
        "customer_id": customer.customer_id,
        "name": f"{customer.first_name} {customer.last_name}",
        "age": customer.age,
        "monthly_income": customer.monthly_income,
        "approved_limit": customer.approved_limit,
        "phone_number": customer.phone_number,
    }

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def check_eligibility_view(request):
    serializer = CheckEligibilitySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    customer_id = serializer.validated_data["customer_id"]
    loan_amount = serializer.validated_data["loan_amount"]
    interest_rate = serializer.validated_data["interest_rate"]
    tenure = serializer.validated_data["tenure"]

    # Perform eligibility checks here, accessing Customer data if needed
    data = {
        "customer_id": customer_id,
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "tenure": tenure,
    }

    response_data = check_eligibility_helper(data)

    return response_data


def calculate_credit_score(customer):
    credit_score = 0

    # i. Past Loans paid on time
    past_loans = Loan.objects.filter(customer=customer, emis_paid_on_time=True).count()

    credit_score += past_loans * 5  # Assume each past loan paid on time contributes 5 points

    # ii. No of loans taken in past
    total_loans_taken = Loan.objects.filter(customer=customer).count()

    credit_score += total_loans_taken * 2  # Assume each past loan contributes 2 points

    # iii. Loan activity in the current year
    current_year = date.today().year

    loans_this_year = Loan.objects.filter(customer=customer, date_of_approval__year=current_year).count()

    credit_score += loans_this_year * 3  # Assume each loan taken in the current year contributes 3 points

    # iv. Loan approved volume
    loan_approved_volume = Loan.objects.filter(customer=customer).aggregate(Sum("loan_amount"))["loan_amount__sum"] or 0

    credit_score += loan_approved_volume * 4  # Assume each approved loan contributes 4 points

    return credit_score

def check_eligibility_helper(data):
    customer_id = data["customer_id"]
    loan_amount = data["loan_amount"]
    interest_rate = data["interest_rate"]
    tenure = data["tenure"]

    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        return Response({"message": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    # Calculate credit score
    credit_score = calculate_credit_score(customer)

    # Check loan eligibility based on credit score
    if credit_score > 50:
        corrected_interest_rate = min(interest_rate, 12.0)
    elif 30 < credit_score <= 50:
        corrected_interest_rate = min(interest_rate, 16.0)
    elif 10 < credit_score <= 30:
        corrected_interest_rate = min(interest_rate, 20.0)
    else:
        return Response(
            {
                "approval": False,
                "message": "Loan not approved due to low credit score.",
            },
            status=status.HTTP_200_OK,
        )

    # Check if sum of all current EMIs > 50% of monthly salary
    sum_current_emis = Loan.objects.filter(customer=customer, loan_approved=True).aggregate(Sum("monthly_repayment"))["monthly_repayment__sum"] or 0

    emis_ratio = sum_current_emis / (0.5 * customer.monthly_income)

    if emis_ratio > 1:
        return Response(
            {
                "approval": False,
                "message": "Loan not approved due to high existing EMIs.",
            },
            status=status.HTTP_200_OK,
        )

    # Calculate monthly installment
    monthly_repayment = calculate_monthly_repayment(loan_amount, corrected_interest_rate, tenure)

    return Response(
        {
            "approval": True,
            "interest_rate": interest_rate,
            "corrected_interest_rate": corrected_interest_rate,
            "tenure": tenure,
            "monthly_repayment": monthly_repayment,
        },
        status=status.HTTP_200_OK,
    )

def calculate_monthly_repayment(loan_amount, annual_interest_rate, tenure, compounding_frequency=12):
    monthly_interest_rate = annual_interest_rate / (compounding_frequency * 100)

    total_compounding_periods = compounding_frequency * tenure

    compound_factor = (1 + monthly_interest_rate) ** total_compounding_periods

    if compound_factor == 1:
        raise ValueError("Invalid input: Compound factor is 1, causing division by zero")

    monthly_repayment = (loan_amount * monthly_interest_rate * compound_factor) / (compound_factor - 1)

    return monthly_repayment


@api_view(["POST"])
def create_loan_view(request):
    data = request.data

    # Check eligibility
    eligibility_result = check_eligibility_helper(data)

    if eligibility_result.status_code == 200:
        # If customer is not eligible, return the eligibility result
        if not eligibility_result.data["approval"]:
            return eligibility_result

        # If eligible, create a new Loan instance
        end_date = date.today() + relativedelta(months=data["tenure"])

        payload = {
            "customer_id": data["customer_id"],
            "loan_amount": data["loan_amount"],
            "interest_rate": eligibility_result.data["interest_rate"],
            "tenure": eligibility_result.data["tenure"],
            "monthly_repayment": eligibility_result.data["monthly_repayment"],
            "emis_paid_on_time": 0,
            "end_date": end_date,
            "date_of_approval": date.today(),
            "loan_approved": True,
        }

        loan_serializer = LoanSerializer(data=payload)
        loan_serializer.is_valid(raise_exception=True)
        loan_serializer.save()

        # Get the newly created Loan instance
        loan_instance = Loan.objects.get(loan_id=loan_serializer.data["loan_id"])

        # Prepare the response data
        response_data = {
            "loan_id": loan_instance.loan_id,
            "customer_id": loan_instance.customer.customer_id,
            "loan_approved": True,
            "message": "Loan approved",
            "monthly_installment": loan_instance.monthly_repayment,
        }
    else:
        return eligibility_result

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def view_loan(request, loan_id):
    try:
        loan_instance = Loan.objects.get(loan_id=loan_id)
        serializer = LoanViewSerializer(loan_instance)

        customer_data = {
            "customer_id": loan_instance.customer.customer_id,
            "name": f"{loan_instance.customer.first_name} {loan_instance.customer.last_name}",
            "age": loan_instance.customer.age,
            "monthly_income": loan_instance.customer.monthly_income,
            "approved_limit": loan_instance.customer.approved_limit,
            "phone_number": loan_instance.customer.phone_number,
        }

        response_data = {
            "loan_id": serializer.data["loan_id"],
            "loan_amount": serializer.data["loan_amount"],
            "interest_rate": serializer.data["interest_rate"],
            "tenure": serializer.data["tenure"],
            "monthly_repayment": serializer.data["monthly_repayment"],
            "emis_paid_on_time": serializer.data["emis_paid_on_time"],
            "end_date": serializer.data["end_date"],
            "date_of_approval": serializer.data["date_of_approval"],
            "loan_approved": serializer.data["loan_approved"],
            "customer": customer_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
    except Loan.DoesNotExist:
        return Response({"message": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def view_loans_by_customer(request, customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id)
        loans = Loan.objects.filter(customer=customer)
        serializer = LoanViewSerializer(loans, many=True)

        response_data = []
        for loan_data in serializer.data:
            loan_details = {
                "loan_id": int(loan_data["loan_id"]),
                "loan_amount": float(loan_data["loan_amount"]),
                "interest_rate": float(loan_data["interest_rate"]),
                "monthly_installment": float(loan_data["monthly_repayment"]),
                "repayments_left": int(loan_data["emis_paid_on_time"]),
            }
            response_data.append(loan_details)

        return Response(response_data, status=status.HTTP_200_OK)
    except Customer.DoesNotExist:
        return Response({"message": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
