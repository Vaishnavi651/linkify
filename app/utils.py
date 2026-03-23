import string
import random

ALPHABET = string.digits + string.ascii_letters

def generate_random_code(length=6):
    return ''.join(random.choices(ALPHABET, k=length))