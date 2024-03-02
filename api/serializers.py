from rest_framework import serializers
from .models import Customer, Loan


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["first_name", "last_name", "age", "monthly_income", "phone_number"]


class CheckEligibilitySerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.FloatField()
    interest_rate = serializers.FloatField()
    tenure = serializers.IntegerField()


class LoanSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.all(), write_only=True
    )
    customer = CustomerSerializer(read_only=True)

    class Meta:
        model = Loan
        fields = "__all__"


class LoanViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = "__all__"
