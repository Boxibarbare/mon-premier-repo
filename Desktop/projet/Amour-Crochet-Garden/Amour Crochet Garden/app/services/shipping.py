"""Shipping fee helpers."""

SHIPPING_FEE = 5.0
FREE_SHIPPING_THRESHOLD = 50.0


def cart_subtotal(cart: list[dict]) -> float:
    return round(sum(float(i["price"]) * int(i["qty"]) for i in cart), 2)


def shipping_fee_for(subtotal: float) -> float:
    """5 € de livraison, gratuit à partir de 50 € de commande."""
    return 0.0 if float(subtotal) >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE


def order_totals(cart: list[dict]) -> tuple[float, float, float]:
    """Return (subtotal, shipping_fee, total)."""
    subtotal = cart_subtotal(cart)
    shipping = shipping_fee_for(subtotal)
    total = round(subtotal + shipping, 2)
    return subtotal, shipping, total
