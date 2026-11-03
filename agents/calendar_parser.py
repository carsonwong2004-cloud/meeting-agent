from typing import Dict, Any, List
# 從 langchain_community 導入本地 Ollama 模型
from langchain_ollama import ChatOllama
import json
import os
from models import Participant, TimeSlot


def load_prompt(filename: str) -> str:
    """Load prompt template from file."""
    prompt_path = os.path.join("prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def calendar_parser_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse natural language calendar input into structured Participant objects.
    
    Args:
        state: Contains meeting_state with raw_input field
        
    Returns:
        Updated state with parsed participants
    """
    from models import MeetingState
    
    meeting_state = MeetingState(**state["meeting_state"])
    messages = state.get("messages", [])
    
    # Load prompt template
    prompt_template = load_prompt("parser.txt")
    
    # === 1. 初始化本地 Ollama 模型（自動讀取 .env 中的 deepseek-r1:7b） ===
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
    
    llm = ChatOllama(
        base_url=base_url,
        model=model_name,
        temperature=0
    )
    
    try:
                # === 2. 安全格式化提示詞 ===
        PLACEHOLDER = "<<<USER_INPUT>>>"
        
        formatted_prompt = prompt_template.replace(PLACEHOLDER, meeting_state.raw_input)
        
        # GUARD: Fail loudly if placeholder wasn't found
        if PLACEHOLDER in formatted_prompt:
            raise ValueError(f"Placeholder {PLACEHOLDER} not found in parser.txt — check prompts/parser.txt")
        
        # GUARD: Verify user input actually made it into the prompt
        if meeting_state.raw_input.strip() and meeting_state.raw_input.strip() not in formatted_prompt:
            raise ValueError(f"User input did not reach prompt. Check placeholder matching.")
        
        # DEBUG: Print what the model will actually see
        print("=" * 70)
        print("USER INPUT:", repr(meeting_state.raw_input))
        print("-" * 70)
        print("PROMPT SENT TO MODEL:")
        print(formatted_prompt[:500], "...[truncated]")
        print("=" * 70)
        
        # === 3. 呼叫本地大模型 ===
        result = llm.invoke(formatted_prompt)
        content = result.content.strip()
        
        # === 🛠️ DeepSeek 特殊處理：過濾掉 <think> 標籤 ===
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        
        # 這裡在後台終端機印出過濾後的原始輸出，方便您追蹤 debug
        print(f"\n[Ollama {model_name} 輸出結果]:\n", content)
        
        # === 4. 解析 JSON 回傳值 ===
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        parsed_data = json.loads(content)
        
        # Convert to Participant objects
        participants = []
        for p_data in parsed_data:
            slots = [TimeSlot(**slot) for slot in p_data.get("free_slots", [])]
            score = p_data.get("flexibility_score", p_data.get("flexibility", 5))
            
            participant = Participant(
                name=p_data["name"],
                free_slots=slots,
                constraints=p_data.get("constraints", []),
                flexibility_score=score
            )
            participants.append(participant)
        
        meeting_state.participants = participants
        meeting_state.status = "parsed"
        
        messages.append(f"✅ Calendar Parser: Successfully parsed {len(participants)} participants")
        for p in participants:
            messages.append(f"   • {p}")
        
    except json.JSONDecodeError as e:
        messages.append(f"❌ Calendar Parser: Failed to parse JSON - {str(e)}")
        messages.append(f"   LLM output was: {content[:200]}")
        meeting_state.status = "parse_failed"
        
    except Exception as e:
        messages.append(f"❌ Calendar Parser: Error - {str(e)}")
        meeting_state.status = "parse_failed"
    
    state["meeting_state"] = meeting_state.model_dump()
    state["messages"] = messages
    
    return state
