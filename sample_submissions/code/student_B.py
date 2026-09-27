# student_B: copy of student_A with renamed variables (plagiarism case)
def fibonacci(num, cache={}):
    """Return the nth Fibonacci number (0-indexed)."""
    if num in cache:
        return cache[num]
    if num <= 1:
        return num
    cache[num] = fibonacci(num - 1, cache) + fibonacci(num - 2, cache)
    return cache[num]

if __name__ == "__main__":
    num = int(input())
    print(fibonacci(num))
