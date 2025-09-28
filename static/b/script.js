const userIdKey = "user_id";
let userId = localStorage.getItem(userIdKey);
if (!userId) {
  userId = crypto.randomUUID();
  localStorage.setItem(userIdKey, userId);
}
document.getElementById("user_id").value = userId;

const form = document.getElementById("chat-form");
const chatBox = document.getElementById("chat-box");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const messageInput = document.getElementById("message");
  const message = messageInput.value;
  messageInput.value = "";

  addMessage("나", message);

  const formData = new FormData();
  formData.append("user_id", userId);
  formData.append("message", message);
  formData.append("artifact_id", "b"); // 유물 B 구분자 추가

  const res = await fetch("/chat", {
    method: "POST",
    body: formData,
  });

  const data = await res.json();
  addMessage("유물 B", data.response || "[응답 없음]");

  if (data.audio_url) {
    const audio = new Audio(data.audio_url);
    audio.play();
  }
});

function addMessage(sender, text) {
  const p = document.createElement("p");
  p.innerText = `${sender}: ${text}`;
  chatBox.appendChild(p);
}
