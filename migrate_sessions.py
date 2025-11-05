#!/usr/bin/env python3
"""
세션 파일 마이그레이션 스크립트

Fallback 경로에 저장된 세션 파일들을 프로젝트별 경로로 이동합니다.
"""

import json
import shutil
from pathlib import Path

def main():
    """메인 마이그레이션 함수"""

    # Fallback 경로
    fallback_dir = Path.home() / ".claude-flow" / "web-sessions"

    if not fallback_dir.exists():
        print("❌ Fallback 세션 디렉토리가 없습니다.")
        return

    # 세션 파일 목록
    session_files = list(fallback_dir.glob("*.json"))

    if not session_files:
        print("✅ 마이그레이션할 세션이 없습니다.")
        return

    print(f"📦 {len(session_files)}개의 세션 파일 발견\n")

    # 세션 파일별 처리
    migrated_count = 0
    skipped_count = 0

    for session_file in session_files:
        try:
            # 세션 파일 읽기
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # project_path 확인
            project_path = data.get("project_path")
            workflow_name = data.get("workflow", {}).get("name", "Unknown")
            session_id = data.get("session_id", session_file.stem)

            if project_path is None:
                print(f"⚠️  세션 {session_id[:8]}... (워크플로우: {workflow_name})")
                print(f"   project_path가 없습니다. 건너뜁니다.\n")
                skipped_count += 1
                continue

            # 프로젝트 이름 추출
            project_name = Path(project_path).name

            # 올바른 경로
            correct_dir = Path.home() / ".claude-flow" / project_name / "web-sessions"
            correct_path = correct_dir / session_file.name

            # 이미 존재하면 건너뛰기
            if correct_path.exists():
                print(f"⏭️  세션 {session_id[:8]}... 이미 존재합니다. 건너뜁니다.\n")
                skipped_count += 1
                continue

            # 디렉토리 생성
            correct_dir.mkdir(parents=True, exist_ok=True)

            # 파일 이동
            shutil.move(str(session_file), str(correct_path))

            print(f"✅ 세션 {session_id[:8]}... 마이그레이션 완료")
            print(f"   워크플로우: {workflow_name}")
            print(f"   {session_file} →")
            print(f"   {correct_path}\n")

            migrated_count += 1

        except Exception as e:
            print(f"❌ 세션 {session_file.name} 마이그레이션 실패: {e}\n")
            skipped_count += 1

    # 요약
    print("=" * 60)
    print(f"마이그레이션 완료: {migrated_count}개")
    print(f"건너뜀: {skipped_count}개")

    # Fallback 디렉토리 정리
    remaining_files = list(fallback_dir.glob("*.json"))
    if not remaining_files:
        print(f"\n🗑️  Fallback 디렉토리가 비었습니다. 삭제하시겠습니까?")
        print(f"   {fallback_dir}")
        response = input("삭제하려면 'yes' 입력: ")
        if response.lower() == "yes":
            fallback_dir.rmdir()
            print("✅ Fallback 디렉토리 삭제 완료")
    else:
        print(f"\n⚠️  Fallback 디렉토리에 {len(remaining_files)}개 파일이 남아있습니다.")


if __name__ == "__main__":
    main()
