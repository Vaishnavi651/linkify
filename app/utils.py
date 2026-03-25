import string
import random

ALPHABET = string.digits + string.ascii_letters

def generate_random_code(length=6):
    """Generate random short code"""
    return ''.join(random.choices(ALPHABET, k=length))

def encode_base62(num: int):
    """Convert number to base62"""
    if num == 0:
        return ALPHABET[0]
    
    result = []
    base = len(ALPHABET)
    
    while num > 0:
        num, rem = divmod(num, base)
        result.append(ALPHABET[rem])
    
    return ''.join(reversed(result))