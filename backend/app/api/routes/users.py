from app.core.security import hashPassword
from app.models import User
from sqlmodel import Session, select

def createUser(session: Session, email: str, password: str):
    user = User(
        email=email,
        hashedPassword=hashPassword(password)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def getUserByEmail(session: Session, email: str):
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()