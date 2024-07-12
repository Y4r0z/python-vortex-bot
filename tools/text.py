
def formatCoins(value: int):
    n = abs(value)
    n %= 100
    if n >= 5 and n <= 20: return f'{value:,} коинов'
    n %= 10
    if n == 1: return f'{value:,} коин'
    if n >= 2 and n <= 4: return f'{value:,} коина'
    return f'{value:,} коинов'
