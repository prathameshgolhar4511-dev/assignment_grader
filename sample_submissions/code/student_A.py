# student_A: clean memoized solution using a cache dict
def fib(n, memo={}):
    """Return the nth Fibonacci number (0-indexed)."""
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib(n - 1, memo) + fib(n - 2, memo)
    return memo[n]

if __name__ == "__main__":
    n = int(input())
    print(fib(n))
