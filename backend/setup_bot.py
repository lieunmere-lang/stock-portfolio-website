"""Discord 봇 채널 설정 스크립트. 채널 ID를 입력���면 BotConfig에 저장."""

from database import BotConfig, engine, init_db
from sqlalchemy.orm import Session

init_db()

print("=== Discord 금융봇 채널 설정 ===")
print("디스코드 서버에서 채널 ID를 복사해주세요.")
print("(채널 우클릭 → ID 복사, 개발자 모드 필요)\n")

modules = [
    ("finance.news", "#뉴스리포트 채널 ID"),
    ("finance.alert", "#가격알림 채널 ID"),
    ("finance.indicator", "#시장지표 채널 ID"),
]

with Session(engine) as session:
    for module_name, prompt in modules:
        channel_id = input(f"{prompt}: ").strip()
        if not channel_id:
            print("  → 건너뜀")
            continue

        existing = session.query(BotConfig).filter_by(module_name=module_name).first()
        if existing:
            existing.channel_id = channel_id
            existing.is_active = True
        else:
            session.add(BotConfig(module_name=module_name, channel_id=channel_id))

    session.commit()
    print("\n✅ 설정 완료!")
