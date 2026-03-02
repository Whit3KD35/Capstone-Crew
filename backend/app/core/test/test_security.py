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

def test_encrypt_decrypt_cycle():
    original = "John Doe Sensitive Info"
    encrypted = encryptData(original)

    # Ensure encryption actually changed the value
    assert encrypted != original

    # Ensure decryption restores original value
    decrypted = decryptData(encrypted)
    assert decrypted == original


def test_multiple_fields_encryption():
    fields = [
        "john@example.com",
        "9725551234",
        "Stage 3 CKD",
        "1.42",
        "88"
    ]

    for field in fields:
        encrypted = encryptData(field)
        assert encrypted != field
        assert decryptData(encrypted) == field