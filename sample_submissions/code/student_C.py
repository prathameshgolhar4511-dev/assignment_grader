# student_C: iterative bottom-up approach, correct but no docstring
def fib(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

print(fib(int(input())))
