"""
Display 설정 스키마

웹 UI Display 설정 관련 스키마를 정의합니다.
"""

from typing import List
from pydantic import BaseModel, Field


class DisplayConfig(BaseModel):
    """
    웹 UI Display 설정

    프로젝트 디렉토리의 .claude-flow/display-config.json에 저장됩니다.

    Attributes:
        left_sidebar_open: 왼쪽 사이드바 열림 상태
        right_sidebar_open: 오른쪽 사이드바 열림 상태
        expanded_sections: 확장된 섹션 목록 (NodePanel)
    """

    left_sidebar_open: bool = Field(default=True, description="왼쪽 사이드바 열림 상태")
    right_sidebar_open: bool = Field(default=True, description="오른쪽 사이드바 열림 상태")
    expanded_sections: List[str] = Field(
        default_factory=lambda: [
            "input",
            "manager",
            "advanced",
            "general",
            "specialized",
            "custom",
        ],
        description="확장된 섹션 목록 (NodePanel)",
    )


class DisplayConfigLoadResponse(BaseModel):
    """
    Display 설정 로드 응답

    Attributes:
        config: Display 설정
    """

    config: DisplayConfig = Field(..., description="Display 설정")


class DisplayConfigSaveRequest(BaseModel):
    """
    Display 설정 저장 요청

    Attributes:
        config: 저장할 Display 설정
    """

    config: DisplayConfig = Field(..., description="저장할 Display 설정")
