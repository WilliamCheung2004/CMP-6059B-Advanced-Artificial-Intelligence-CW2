import { useState } from "react"

export default function ChatInput({ sendMessage }) {
    const [text, setText] = useState("")

    function handleSend() {
        if (!text.trim()) return 
        sendMessage(text)
        setText("")
    }

    function handleKeyPress(e) {
        if (e.key === "Enter") {
            handleSend()
        }
    }

    return (
        <div className="chatInput">
            <button className="iconBtn">
                📅
            </button>

            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={handleKeyPress} placeholder="Type a message..." />

            <button className="send" onClick={handleSend}>
                ↑
            </button>

        </div>
    )
}