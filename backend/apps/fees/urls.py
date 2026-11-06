from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("fees/categories", views.FeeCategoryViewSet, basename="fee-categories")
router.register("fees/structures", views.FeeStructureViewSet, basename="fee-structures")
router.register("fees/invoices", views.InvoiceViewSet, basename="fee-invoices")
router.register("fees/payments", views.FeePaymentViewSet, basename="fee-payments")

urlpatterns = router.urls
