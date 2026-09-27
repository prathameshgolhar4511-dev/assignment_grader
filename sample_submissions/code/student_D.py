# student_D: naive recursive — correct for small n but times out on large n
def fib(n):
    if n == 0:
        return 0
    if n == 1:
        return 1
    return fib(n - 1) + fib(n - 2)

print(fib(int(input())))
