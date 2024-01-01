from rest_framework_nested import routers
from . import views


router = routers.DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('carts', views.CartViewSet, basename='cart')
router.register('customers', views.CustomerViewSet, basename='customer')
router.register('orders', views.OrderViewSet, basename='order')

product_router = routers.NestedSimpleRouter(router, 'products', lookup='product')
product_router.register('comments', views.CommentViewSet, basename='product_comment')

Cart_item_router = routers.NestedSimpleRouter(router, 'carts', lookup='cart')
Cart_item_router.register('items', views.CartItemViewSet, basename='cart_item')

urlpatterns = router.urls + product_router.urls + Cart_item_router.urls




