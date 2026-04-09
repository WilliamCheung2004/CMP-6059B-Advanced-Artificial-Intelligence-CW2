import { useState, useEffect, useRef } from "react"
import Message from "../components/Message"
import ChatInput from "../components/ChatInput"
import "../styles/chat.css"

export default function ChatPage() {
    const [messages, setMessages] = useState([
        { text: "Hello! I'm TrainBot. How can I help you today?", sender: "bot" }
    ])

    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behaviour: "smooth"})
    }, [messages])

    async function sendMessage(text) {
        const newMessages = [...messages, {text, sender: "user"}]
        setMessages(newMessages)
        try {
            const response = await fetch("http://localhost:5000/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ message:text })
            })

            const data = await response.json()

            setMessages([
                ...newMessages, 
                { text: data.reply, sender: "bot" }
            ])

        } catch {
            setMessages([
                ...newMessages, 
                { text: "Backend is not connected", sender: "bot" }
            ])
        }
    }
    
return (
    <div className="chatContainer">


            <div className="chatBox">
                <div className="chatHeader">
                    TrainBot
                </div>

                <div className="chatMessages">
                    {messages.map((msg, i) => (
                        <Message key={i} text={msg.text} sender={msg.sender} />
                    ))}
                    <div ref={bottomRef}></div>
                </div>

                <ChatInput sendMessage={sendMessage} />
            </div>

        </div>

)
}