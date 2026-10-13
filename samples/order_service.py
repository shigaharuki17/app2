"""订单金额计算模块：演示类型提示、异常和类方法的文档生成。"""
from dataclasses import dataclass
from decimal import Decimal

TAX_RATE = Decimal("0.06")


@dataclass
class OrderItem:
    """一项订单商品，保存名称、单价和数量。"""
    name: str
    price: Decimal
    quantity: int = 1

    def subtotal(self) -> Decimal:
        """计算商品小计。单价和数量不能为负。"""
        if self.price < 0 or self.quantity < 0:
            raise ValueError("价格和数量不能为负")
        return self.price * self.quantity


def calculate_total(items: list[OrderItem], discount: Decimal = Decimal("0")) -> Decimal:
    """计算折扣后含税总额，折扣必须在 0 到 1 之间。"""
    if not Decimal("0") <= discount <= Decimal("1"):
        raise ValueError("折扣必须在 0 到 1 之间")
    subtotal = sum((item.subtotal() for item in items), Decimal("0"))
    return (subtotal * (1 - discount) * (1 + TAX_RATE)).quantize(Decimal("0.01"))


if __name__ == "__main__":
    print(calculate_total([OrderItem("笔记本", Decimal("12.50"), 2)]))
