from decimal import Decimal

from django.utils.text import slugify
from django.db import transaction

from rest_framework import serializers


from store.models import Category, Product, Comment, Cart, CartItem, Customer, Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    num_of_products = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['title', 'description', 'top_product', 'num_of_products']

    def validate(self, data):
        if len(data['title']) < 3:
            raise serializers.ValidationError('Title length must be at least 3')

    def get_num_of_products(self, category):
        return category.products_count


class ProductSerializer(serializers.ModelSerializer):
    unit_price_after_tax = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['name', 'unit_price', 'unit_price_after_tax', 'category', 'inventory', 'description']

    def get_unit_price_after_tax(self, product):
        return round(product.unit_price * Decimal(1.09), 2)

    def validate(self, data):
        if len(data['name']) < 5:
            raise serializers.ValidationError('name length should be latest 6')
        return data

    def create(self, validated_data):
        product = Product(**validated_data)
        product.slug = slugify(product.name)
        product.save()
        return product


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['name', 'body', 'datetime_created']

    def create(self, validated_data):
        return Comment.objects.create(product_id=self.context['product_pk'], **validated_data)


class CartItemProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'unit_price']


class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['quantity']


class AddCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity']

    def create(self, validated_data):
        cart_id = self.context['cart_pk']

        product = validated_data.get('product')
        quantity = validated_data.get('quantity')

        try:
            cart_item = CartItem.objects.get(cart_id=cart_id, product_id=product.id)
            cart_item.quantity += quantity
            cart_item.save()
            return cart_item
        except CartItem.DoesNotExist:
            cart_item = CartItem.objects.create(cart_id=self.context['cart_pk'], **validated_data)
        self.instance = cart_item
        return cart_item


class CartItemSerializer(serializers.ModelSerializer):
    product = CartItemProductSerializer(read_only=True)
    item_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'item_price']

    def get_item_price(self, cart_item):
        return cart_item.product.unit_price * cart_item.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    cart_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'cart_price']
        read_only_fields = ['id']

    def get_cart_price(self, cart):
        return sum([item.product.unit_price * item.quantity for item in cart.items.all()])


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'user', 'phone_number', 'birth_date']
        read_only_fields = ['user']


class OrderItemProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'unit_price']


class OrderItemSerializer(serializers.ModelSerializer):
    product = OrderItemProductSerializer()

    class Meta:
        model = OrderItem
        fields = ['order', 'product', 'quantity', 'unit_price']
        read_only_fields = ['order', 'quantity', 'unit_price']


class OrderCustomerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')

    class Meta:
        model = Customer
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 'birth_date']


class OrderAdminSerializer(serializers.ModelSerializer):
    customer = OrderCustomerSerializer()
    items = OrderItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'customer', 'datetime_created', 'status', 'items', 'total_price']

    def get_total_price(self, order):
        return sum(item.unit_price for item in order.items.all())


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'customer', 'datetime_created', 'status', 'items', 'total_price']

    def get_total_price(self, order):
        return sum(item.unit_price for item in order.items.all())


class OrderCreateSerializer(serializers.Serializer):
    cart_id = serializers.UUIDField()

    def validate_cart_id(self, cart_id):
        try:
            if Cart.objects.prefetch_related('items').get(id=cart_id).items.count() == 0:
                raise serializers.ValidationError('Your cart is empty.')
            else:
                return cart_id
        except Cart.DoesNotExist:
            raise serializers.ValidationError('There is no cart with this cart id.')

    def save(self, **kwargs):
        with transaction.atomic():
            cart_id = self.validated_data['cart_id']
            user_id = self.context['user_id']
            customer = Customer.objects.get(user_id=user_id)

            cart_items = CartItem.objects.filter(cart_id=cart_id)

            order = Order()
            order.customer = customer
            order.save()

            order_items = [
                OrderItem(
                    order=order,
                    product=cart_item.product,
                    unit_price=cart_item.product.unit_price,
                    quantity=cart_item.quantity,
                ) for cart_item in cart_items
            ]

            OrderItem.objects.bulk_create(order_items)

            Cart.objects.filter(id=cart_id).delete()
            return order
