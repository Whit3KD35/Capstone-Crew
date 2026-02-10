from app.core.security import (
    hashPassword,
    verifyPassword,
    encryptData,
    decryptData
)

def testPasswordHashing():
    password = "TestPass123!"
    hashed = hashPassword(password)

    assert hashed != password
    assert verifyPassword(password, hashed)
    assert not verifyPassword("wrongpassword", hashed)

def testDataEncryption():
    data = "Sensitive patient data"
    encrypted = encryptData(data)

    assert encrypted != data
    decrypted = decryptData(encrypted)
    assert decrypted == data
