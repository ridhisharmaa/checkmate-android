from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_current_teacher, hash_password, verify_password
from app.db import get_db
from app.models.teacher import Teacher
from app.schemas.auth import LoginRequest, SignupRequest, TeacherResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = (await db.execute(select(Teacher).where(Teacher.email == body.email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="an account with this email already exists")

    teacher = Teacher(email=body.email, password_hash=hash_password(body.password))
    db.add(teacher)
    await db.commit()
    return TokenResponse(access_token=create_access_token(teacher.id))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    teacher = (await db.execute(select(Teacher).where(Teacher.email == body.email))).scalar_one_or_none()
    if teacher is None or not verify_password(body.password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="incorrect email or password")
    return TokenResponse(access_token=create_access_token(teacher.id))


@router.get("/me", response_model=TeacherResponse)
async def me(teacher: Teacher = Depends(get_current_teacher)) -> TeacherResponse:
    return TeacherResponse(id=teacher.id, email=teacher.email)
