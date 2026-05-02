"""User personalization profiles management.

Profiles are stored in the `user_profiles` collection in MongoDB.
Each user has a single profile document.
"""

from __future__ import annotations
import logging
from src.core.schemas import UserProfile

logger = logging.getLogger(__name__)


async def get_profile(user_id: str) -> UserProfile:
    """Return the profile for ``user_id`` or a default profile.

    DB-only logic: check MongoDB via user_repo.
    """
    # Lazy import to avoid circular dependency
    from src.core.dependencies import container
    try:
        user_doc = await container.user_repo.find_by_id(user_id)
        db_profile = await container.user_repo.get_profile(user_id)
        
        profile_data = db_profile.model_dump() if db_profile else {}
        if user_doc:
            profile_data["username"] = user_doc.username
            profile_data["email"] = user_doc.email
            
        return UserProfile.model_validate(profile_data)
    except Exception:
        logger.exception("Error fetching profile from DB for user_id=%s", user_id)

    # Return default profile if not found in DB
    return UserProfile()


def build_personalized_prompt(template: str, profile: UserProfile, current_timestamp: str | None = None) -> str:
    """Inject personality, tone, and user context into a prompt template."""
    prompt = template
    
    if current_timestamp:
        prompt = prompt.replace("{{CURRENT_TIMESTAMP}}", current_timestamp)
    
    # Personality Mapping
    pers_map = {
        "encouraging": "Thái độ của bạn: Luôn tích cực, khích lệ người dùng. Hãy khen ngợi khi họ tiết kiệm và động viên nhẹ nhàng khi họ chi tiêu nhiều.",
        "objective": "Thái độ của bạn: Khách quan, trung lập. Chỉ tập trung vào số liệu và sự thật, không đưa ra cảm xúc cá nhân.",
        "strict": "Thái độ của bạn: Nghiêm khắc và kỷ luật. Hãy nhắc nhở người dùng về trách nhiệm tài chính, phê bình nếu họ chi tiêu lãng phí hoặc vượt ngân sách."
    }
    
    # Tone Mapping
    tone_map = {
        "friendly": "Phong cách trò chuyện: Thân thiện, gần gũi như một người bạn, xưng hô phù hợp (ví dụ: mình - bạn, em - anh/chị).",
        "playful": "Phong cách trò chuyện: Vui vẻ, hóm hỉnh, thỉnh thoảng có thể dùng icon và pha trò nhẹ nhàng.",
        "formal": "Phong cách trò chuyện: Lịch sự, trang trọng, xưng hô chuẩn mực.",
        "concise": "Phong cách trò chuyện: Ngắn gọn, súc tích, đi thẳng vào vấn đề, tránh rườm rà."
    }
    
    p_instr = pers_map.get(profile.assistant_personality, pers_map["encouraging"])
    t_instr = tone_map.get(profile.communication_tone, tone_map["friendly"])
    
    # User Context (Name, occupation, hobbies)
    user_context = []
    if profile.display_name:
        user_context.append(f"Tên của người dùng là: {profile.display_name}. Hãy thỉnh thoảng gọi tên họ một cách tự nhiên.")
    if profile.occupation:
        user_context.append(f"Nghề nghiệp: {profile.occupation}.")
    if profile.hobbies:
        user_context.append(f"Sở thích: {', '.join(profile.hobbies)}.")
        
    if user_context:
        p_instr += " " + " ".join(user_context)
        
    prompt = prompt.replace("{{PERSONALITY_INSTRUCTION}}", p_instr)
    prompt = prompt.replace("{{TONE_INSTRUCTION}}", t_instr)
    
    return prompt
