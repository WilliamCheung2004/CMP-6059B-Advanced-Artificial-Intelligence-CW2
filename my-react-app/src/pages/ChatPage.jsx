import { useState, useEffect, useRef } from "react"
import Message from "../components/Message"
import ChatInput from "../components/ChatInput"
import "../styles/chat.css"

export default function ChatPage() {

    const [messages, setMessages] = useState([
        { text: "Hello! I'm TrainBot. How can I help you today?", sender: "bot" }
    ])

    const [headerTitle, setHeaderTitle] = useState("TrainBot")
    const [headerSubtitle, setHeaderSubtitle] = useState("")

    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behaviour: "smooth" })
    }, [messages])

    async function sendMessage(text) {
        const newMessages = [...messages, { text, sender: "user" }]
        setMessages(newMessages)

        try {
            const response = await fetch("http://localhost:5000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            })

            const data = await response.json()

            if (data.context) {
                setHeaderTitle(data.context.title || "TrainBot")
                setHeaderSubtitle(data.context.subtitle || "")
            }

            setMessages([
                ...newMessages,
                {
                    text: data.reply || "I received your message.",
                    sender: "bot",
                    options: data.options || [],
                    tickets: data.tickets || []
                }
            ])

        } catch (error) {
            console.error("Backend connection failed:", error)

            setMessages([
                ...newMessages,
                {
                    text: "Backend not connected. Waiting for API...",
                    sender: "bot"
                }
            ])
        }
    }

    function handleOptionClick(optionText) {
        sendMessage(optionText)
    }

    return (
        <div className="chatContainer">
            <div className="chatBox">
                <div className="chatHeader">
                    <div className="headerText">
                        <span className="headerTitle">{headerTitle}</span>
                        {headerSubtitle && (
                            <span className="headerSubtitle">{headerSubtitle}</span>
                        )}
                    </div>
                </div>

                <div className="chatMessages">
                    {messages.map((msg, i) => (
                        <Message
                            key={i}
                            text={msg.text}
                            sender={msg.sender}
                            options={msg.options || []}
                            tickets={msg.tickets || []}
                            onOptionClick={handleOptionClick}
                            isLatest={false}
                        />
                    ))}
                    <div ref={bottomRef}></div>
                </div>

                <ChatInput sendMessage={sendMessage} />
            </div>
        </div>
    )
}