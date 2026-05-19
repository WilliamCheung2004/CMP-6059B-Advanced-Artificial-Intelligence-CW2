import { useState, useEffect, useRef } from "react"
import Message from "../components/Message"
import ChatInput from "../components/ChatInput"
import "../styles/chat.css"

export default function ChatPage() {

    const [sessionId, setSessionId] = useState(() => {
        const stored = localStorage.getItem('trainbot_session')
        if (stored) return stored
        const newId = crypto.randomUUID()
        localStorage.setItem('trainbot_session', newId)
        return newId
    })
    
    useEffect(() => {
        localStorage.setItem('trainbot_session', sessionId)
    }, [sessionId])

    const [messages, setMessages] = useState(() => {
        const saved = localStorage.getItem('trainbot_messages')
        if (saved) {
            try {
                return JSON.parse(saved)
            } catch {}
        }
        return [
            { text: "Hello! I'm TrainBot. How can I help you today?", sender: "bot"}
        ]
    })

    const [headerTitle, setHeaderTitle] = useState(() => {
        return localStorage.getItem('trainbot_headerTitle') || "TrainBot" 
    })

    const [headerSubtitle, setHeaderSubtitle] = useState(() => {
        return localStorage.getItem('trainbot_headerSubtitle') || ""
    })

    useEffect(() => {
        localStorage.setItem('trainbot_messages', JSON.stringify(messages))
    }, [messages])

    useEffect(() => {
        localStorage.setItem('trainbot_headerTitle', headerTitle)
    }, [headerTitle])

    useEffect(() => {
        localStorage.setItem('trainbot_headerSubtitle', headerSubtitle)
    }, [headerSubtitle])

    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behaviour: "smooth" })
    }, [messages])

    const [sending, setSending] = useState(false)

    const restartConversation = async () => {
        const newSessionId = crypto.randomUUID()
        setSessionId(newSessionId)
        localStorage.setItem('trainbot_session', newSessionId)

        const welcomeMessages = [
            { text: "Hello! I'm TrainBot. How can I help you today?", sender: "bot"}
        ]
        setMessages(welcomeMessages)
        localStorage.setItem('trainbot_messages', JSON.stringify(welcomeMessages))

        setHeaderTitle("TrainBot")
        setHeaderSubtitle("")
        localStorage.setItem('trainbot_headerTitle', "TrainBot")
        localStorage.setItem('trainbot_headerSubtitle', "")

        try {
            await fetch("http://localhost:5000/restart", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    old_session_id: sessionId,
                    new_session_id: newSessionId
                })
            })
        } catch (error) {
            console.error("Failed to notify backend of restart:", error)
        }
    }

    async function sendMessage(text) {

        if (sending) return 

        const newMessages = [...messages, { text, sender: "user" }]
        setMessages(newMessages)

        setSending(true)

        try {
            const response = await fetch("http://localhost:5000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, session_id: sessionId })
            })

            const data = await response.json()

            if (data.context) {
                setHeaderTitle(data.context.title || "TrainBot")
                setHeaderSubtitle(data.context.subtitle || "")
            }

            setMessages([
                ...newMessages,
                {
                    text: data.reply || "",
                    sender: "bot",
                    options: data.options || [],
                    tickets: data.tickets || [],
                    postMessage: data.postMessage || ""
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
        } finally {
            setSending(false)
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
                    <button className="restartBtn" onClick={restartConversation} title="Restart conversation" disabled={sending}>Restart Conversation</button>
                </div>

                <div className="chatMessages">
                    {messages.map((msg, i) => (
                        <Message
                            key={i}
                            text={msg.text}
                            sender={msg.sender}
                            options={msg.options || []}
                            tickets={msg.tickets || []}
                            postMessage={msg.postMessage || ""}
                            onOptionClick={handleOptionClick}
                            isLatest={false}
                        />
                    ))}
                    <div ref={bottomRef}></div>
                </div>

                <ChatInput sendMessage={sendMessage} disabled={sending} />
            </div>
        </div>
    )
}