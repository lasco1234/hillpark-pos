from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Customer
from .forms import CustomerForm


@login_required
def add_customer(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST, user=request.user)   # ← Pass user
        if form.is_valid():
            customer = form.save(commit=False)
            
            if not request.user.can_see_all and request.user.store:
                customer.store = request.user.store
                
            customer.save()
            messages.success(request, 'Customer added successfully.')
            return redirect('add_customer')
    else:
        form = CustomerForm(user=request.user)   # ← Pass user

    # Stats (respect store isolation)
    if request.user.can_see_all:
        customers = Customer.objects.all()
    else:
        customers = Customer.objects.filter(store=request.user.store)

    context = {
        'form': form,
        'total_customers': customers.count(),
        'company_customers': customers.filter(customer_type='Company').count(),
        'group_customers': customers.filter(customer_type='Group').count(),
        'individual_customers': customers.filter(customer_type='Individual').count(),
        'school_customers': customers.filter(customer_type='School').count(),
    }
    return render(request, 'customer/add_customer.html', context)


@login_required
def customer_list(request):
    customer_type = request.GET.get('type')
    
    if request.user.can_see_all:
        customers = Customer.objects.select_related('store').all()
    else:
        customers = Customer.objects.select_related('store').filter(store=request.user.store)

    if customer_type:
        customers = customers.filter(customer_type=customer_type)

    context = {
        'customers': customers,
        'selected_type': customer_type,
    }
    return render(request, 'customer/customer_list.html', context)