"""Explicit local-only demo data. Never run against a production database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from werkzeug.security import generate_password_hash
from app import app
from studymate.extensions import db
from studymate.models import User, Course, Lecture, Card, ReviewState

if os.getenv("APP_ENV") == "production":
    raise SystemExit("Demo seeding is disabled in production")
with app.app_context():
    if User.query.filter_by(email="demo@studymate.test").first():
        raise SystemExit("Demo account already exists; no changes made")
    user = User(
        email="demo@studymate.test",
        name="체험 학습자",
        password_hash=generate_password_hash("local-demo-only-2026"),
    )
    db.session.add(user)
    db.session.flush()
    for title, description, lectures in [
        (
            "인지심리학",
            "기억과 학습을 이해하는 첫걸음 · 체험 자료",
            ["작업기억과 장기기억", "인출 연습과 간격 효과"],
        ),
        (
            "데이터 사이언스",
            "데이터에서 질문하고 근거를 찾는 공부 · 체험 자료",
            ["확률과 조건부확률"],
        ),
        ("반도체 공정", "소재에서 소자까지 연결하기 · 체험 자료", ["박막 증착의 기초"]),
    ]:
        course = Course(user_id=user.id, title=title, description=description)
        db.session.add(course)
        db.session.flush()
        for title in lectures:
            lecture = Lecture(
                user_id=user.id,
                course_id=course.id,
                title=title,
                topic="체험용 강의입니다. 본인의 강의자료로 공부를 시작하세요.",
            )
            db.session.add(lecture)
            db.session.flush()
            if title == "작업기억과 장기기억":
                for question, answer in [
                    (
                        "인출 연습은 어떤 학습 활동인가요?",
                        "자료를 보지 않고 배운 내용을 기억에서 꺼내는 연습입니다.",
                    ),
                    (
                        "간격을 둔 복습은 어떻게 실천할 수 있나요?",
                        "한 번에 몰아서 반복하기보다 시간을 두고 다시 떠올려봅니다.",
                    ),
                ]:
                    card = Card(
                        user_id=user.id,
                        lecture_id=lecture.id,
                        question=question,
                        answer=answer,
                        concept="학습 전략",
                        explanation="수동 작성된 체험 카드입니다. AI 생성 결과가 아닙니다.",
                    )
                    db.session.add(card)
                    db.session.flush()
                    db.session.add(ReviewState(user_id=user.id, card_id=card.id))
    db.session.commit()
    print("Local demo: demo@studymate.test / local-demo-only-2026")
