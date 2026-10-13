# order_service.py 代码说明

## 模块概览

订单金额计算模块：演示类型提示、异常和类方法的文档生成。

源文件共 31 行，包含 1 个顶层函数、1 个类。

## 依赖与常量

导入模块：` dataclasses `, ` decimal `

顶层常量：` TAX_RATE `

## API 参考

### 类 ` OrderItem `

一项订单商品，保存名称、单价和数量。

继承：无显式基类

### ` calculate_total `

```python
calculate_total(items: list[OrderItem], discount: Decimal=Decimal('0')) -> Decimal
```

计算折扣后含税总额，折扣必须在 0 到 1 之间。

源码位置：第 22–27 行。

直接调用（静态提取）：` (subtotal * (1 - discount) * (1 + TAX_RATE)).quantize `, ` Decimal `, ` ValueError `, ` item.subtotal `, ` sum `

显式抛出的异常：` ValueError('折扣必须在 0 到 1 之间') `

### ` OrderItem.subtotal `

```python
OrderItem.subtotal(self) -> Decimal
```

计算商品小计。单价和数量不能为负。

源码位置：第 15–19 行。

直接调用（静态提取）：` ValueError `

显式抛出的异常：` ValueError('价格和数量不能为负') `

## 使用与限制

存在主入口保护，可参考源码中的入口调用。

本工具只解析代码，不执行用户源码，不推断运行结果。动态导入、继承解析、外部依赖副作用和嵌套定义不属于本版分析范围。

缺少 docstring 的对象：无

## 来源校验

源码 SHA-256：0d30b9f34384d72ad266a244dc69337542059b3a31576f3df8b466c8d5faebcb