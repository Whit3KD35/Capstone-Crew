"""from passlib.context import CryptContext
from cryptography.fernet import Fernet
import os

pwdContext = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hashPassword(password: str) -> str:
    return pwdContext.hash(password)

def verifyPassword(plainPassword: str, hashedPassword: str) -> bool:
    return pwdContext.verify(plainPassword, hashedPassword)

FERNET_KEY = os.getenv("FERNET_KEY")

if not FERNET_KEY:
    raise RuntimeError("FERNET_KEY not set in environment")

fernet = Fernet(FERNET_KEY.encode())

def encryptData(data: str) -> str:
    return fernet.encrypt(data.encode()).decode()

def decryptData(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
"""

#print(">>> USING app/core/security.py <<<")

from passlib.context import CryptContext
from cryptography.fernet import Fernet
import os

pwdContext = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

MAX_PASSWORD_LENGTH = 72

def hashPassword(password: str) -> str:
    return pwdContext.hash(password)

def verifyPassword(plainPassword: str, hashedPassword: str) -> bool:
    return pwdContext.verify(plainPassword, hashedPassword)

def getFernet() -> Fernet:
    key = os.getenv("FERNET_KEY")
    if not key:
        raise RuntimeError("FERNET_KEY not set in environment")
    return Fernet(key.encode())

def encryptData(data: str) -> str:
    return getFernet().encrypt(data.encode()).decode()

def decryptData(token: str) -> str:
    return getFernet().decrypt(token.encode()).decode()
