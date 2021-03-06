from django.shortcuts import render, redirect, HttpResponse
from django.http import FileResponse
from store.models import Product
from store.forms import CheckoutForm
from django.views.decorators.csrf import csrf_exempt
from store.models import Payment, UserProduct
from math import floor
from django.contrib.auth.decorators import login_required
from gurukul.settings import RAZOPRPAY_KEY, RAZOPRPAY_SECRET, PAYMENT_CALLBACK_URL
import razorpay

client = razorpay.Client(auth=(RAZOPRPAY_KEY, RAZOPRPAY_SECRET))


@login_required()
def download_file(request, slug):
    try:
        product = Product.objects.get(slug=slug)

        userProduct = UserProduct.objects.get(
            product=product, user=request.user)

        return FileResponse(open(product.file.path, "rb"))

    except UserProduct.DoesNotExist:
        return redirect("login")


@csrf_exempt
def payment_verify(request):
    if request.method == "POST":
        print(request.POST)
        razorpay_payment_id = request.POST["razorpay_payment_id"]
        razorpay_order_id = request.POST["razorpay_order_id"]
        razorpay_signature = request.POST["razorpay_signature"]
        params_dict = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        }

        client.utility.verify_payment_signature(params_dict)
        payment = Payment.objects.get(order_id=razorpay_order_id)
        payment.status = "SUCCESS"
        payment.payment_id = razorpay_payment_id
        payment.save()

        user_product = UserProduct(
            user=payment.user, payment=payment, product=payment.product
        )

        user_product.save()
        return render(request, template_name="store/payment_success.html")


def create_payment(request, slug):
    template_name = ""
    context = {}
    form = CheckoutForm(request.POST)
    product = Product.objects.get(slug=slug)
    user = None
    if request.user.is_authenticated:
        user = request.user
    else:
        return redirect("login")
    if form.is_valid():
        print("create payment")
        email = form.cleaned_data.get("email")
        phone = form.cleaned_data.get("phone")
        template_name = "store/checkout.html"
        #       create order here
        price = floor(
            (product.price - (product.price * product.discount * 0.01)))
        order_amount = price * 100
        order_currency = "INR"
        order_receipt = f"order_rcptid_{product.id}_{user.id}"
        notes = {"email": email, "phone": phone}
        data = {
            "amount": order_amount,
            "currency": order_currency,
            "receipt": order_receipt,
            "notes": notes,
        }
        order = client.order.create(data=data)

        # create payment
        payment = Payment(
            product=product, user=user, status="FAIL", order_id=order.get("id")
        )
        payment.save()
        context = {
            "user": user,
            "product": product,
            "order": order,
            "show_payment_dialog": True,
            "form": form,
            "PAYMENT_CALLBACK_URL": PAYMENT_CALLBACK_URL,
        }

    else:
        context = {
            "product": product,
            "form": form,
            "PAYMENT_CALLBACK_URL": PAYMENT_CALLBACK_URL,
        }
        template_name = "store/checkout.html"

    return render(request, template_name=template_name, context=context)
