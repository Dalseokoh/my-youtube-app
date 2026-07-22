
import re
import requests
import streamlit as st

# ── 기본 화면 설정 ─────────────────────────────────────────────
st.set_page_config(page_title="유튜브 댓글 분석기", page_icon="💬", layout="centered")

# 예시로 쓸 두 개의 유튜브 링크
EXAMPLE_1_URL = "https://youtu.be/d95J8yzvjbQ?si=LfL5DLwCL8Pk077r"
EXAMPLE_2_URL = "https://youtu.be/I9vK5EVTt0U?si=NEZ8L7MRuNvrzINa"

# 입력창의 값을 세션 상태(session_state)로 관리한다.
# 이렇게 해야 예시 버튼을 눌렀을 때 입력창 내용을 코드에서 바꿔줄 수 있다.
if "url_input" not in st.session_state:
    st.session_state.url_input = EXAMPLE_1_URL

st.title("💬 유튜브 댓글 분석기")
st.caption("1단계: 유튜브 영상 링크를 넣으면 댓글을 가져와서 좋아요 순으로 보여줘요.")

# ── 예시 버튼 두 개를 나란히 배치 ───────────────────────────────
col1, col2 = st.columns(2)
with col1:
    if st.button("예시 1 · 딥마인드 다큐(영어 댓글)", use_container_width=True):
        st.session_state.url_input = EXAMPLE_1_URL
with col2:
    if st.button("예시 2 · 2002 월드컵 추억(한국어 댓글)", use_container_width=True):
        st.session_state.url_input = EXAMPLE_2_URL

# 링크 입력창 (key를 url_input으로 지정해서 위 session_state와 연결됨)
video_url = st.text_input("유튜브 영상 링크를 붙여넣으세요", key="url_input")


# ── 링크에서 영상 ID만 뽑아내는 함수 ────────────────────────────
def extract_video_id(url: str):
    """
    유튜브 링크에서 11자리 영상 ID만 뽑아낸다.
    - youtu.be/영상ID  형태
    - youtube.com/watch?v=영상ID  형태
    - youtube.com/shorts/영상ID  형태
    모두 처리하며, si= 같이 뒤에 붙는 추가 값은 무시한다.
    못 찾으면 None을 반환한다.
    """
    if not url:
        return None

    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


# ── YouTube Data API로 댓글을 가져오는 함수 ─────────────────────
def fetch_comments(video_id: str, api_key: str):
    """
    commentThreads 엔드포인트에 요청해서 댓글을 최대 100개 가져온다.
    part=snippet, order=relevance(좋아요 많은 순)로 요청한다.
    반환값: (성공 여부, 댓글 리스트 또는 에러 응답(dict))
    """
    endpoint = "https://www.googleapis.com/youtube/v3/commentThreads"
    params = {
        "part": "snippet",
        "videoId": video_id,
        "order": "relevance",   # 최신순이 아니라 인기(좋아요 많은)순
        "maxResults": 100,      # 최대 100개
        "textFormat": "plainText",
        "key": api_key,
    }

    response = requests.get(endpoint, params=params, timeout=10)

    if response.status_code != 200:
        # 실패하면 원본 에러 응답을 그대로 넘겨서 위에서 원인을 파악하게 함
        try:
            return False, response.json()
        except Exception:
            return False, {}

    data = response.json()
    items = data.get("items", [])

    comments = []
    for item in items:
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        comments.append({
            "댓글": snippet.get("textOriginal", ""),
            "좋아요": snippet.get("likeCount", 0),
        })
    return True, comments


# ── 실제 화면 로직 ─────────────────────────────────────────────
if video_url:
    video_id = extract_video_id(video_url)

    if not video_id:
        st.error("⚠️ 링크에서 영상 ID를 찾지 못했어요. 유튜브 링크가 맞는지 다시 확인해주세요.")
    else:
        # secrets 금고에서 API 키 불러오기
        api_key = st.secrets.get("YOUTUBE_API_KEY")

        if not api_key:
            st.error("⚠️ YOUTUBE_API_KEY가 설정되어 있지 않아요. 앱 관리자에게 문의해주세요.")
        else:
            with st.spinner("댓글을 가져오는 중이에요..."):
                success, result = fetch_comments(video_id, api_key)

            if not success:
                # 에러 사유를 최대한 파악해서 친절한 한국어 메시지로 보여줌
                reason = ""
                try:
                    reason = result.get("error", {}).get("errors", [{}])[0].get("reason", "")
                except Exception:
                    pass

                if reason == "commentsDisabled":
                    st.warning("😥 이 영상은 댓글 기능이 꺼져 있어서 댓글을 가져올 수 없어요.")
                elif reason == "videoNotFound":
                    st.warning("😥 영상을 찾을 수 없어요. 링크가 올바른지 다시 확인해주세요.")
                else:
                    st.error("😥 댓글을 가져오는 중 문제가 생겼어요. 링크를 확인하거나 잠시 후 다시 시도해주세요.")
            else:
                comments = result

                if not comments:
                    st.info("이 영상에는 댓글이 없어요.")
                else:
                    # 좋아요 많은 순으로 정렬
                    comments_sorted = sorted(comments, key=lambda c: c["좋아요"], reverse=True)

                    # 가져온 댓글 개수를 큼직한 지표 카드로 표시
                    st.metric("가져온 댓글 개수", f"{len(comments_sorted)}개")

                    # 댓글 목록을 표로 표시 (좋아요 수 포함)
                    st.dataframe(comments_sorted, use_container_width=True, hide_index=True)
