import { useState, useEffect, useRef } from "react"
import Message from "../components/Message"
import ChatInput from "../components/ChatInput"
import "../styles/chat.css"

export default function ChatPage() {

    const DEFAULT_OPTIONS = {
        mainMenu: ["Find Ticket", "Check Delay", "Other"], 
        ticketType: ["Single", "Return"],
    }
    const [messages, setMessages] = useState([
        { text: "Hello! I'm TrainBot. How can I help you today?", sender: "bot", options: DEFAULT_OPTIONS.mainMenu}
    ])

    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behaviour: "smooth"})
    }, [messages])

    function getHardcodedReply(userMessage) {
        const msg = userMessage.toLowerCase()

        if (msg.includes("find ticket") || msg === "find ticket") {
            return {
                reply: "Would you like a ingle or return ticket?", 
                options: DEFAULT_OPTIONS.ticketType
            }
        }

        
    if (msg === "single" || msg === "return") {
        const exampleTickets = [
            {
                origin: "Norwich",
                destination: "London Liverpool Street",
                departureTime: "09:30",
                changes: 1,
                price: 18.23,
                cheapest: false,
                bookingUrl: "#"
            },
            {
                origin: "Norwich",
                destination: "London Liverpool Street",
                departureTime: "09:45",
                changes: 3,
                price: 15.34,
                cheapest: true,
                bookingUrl: "#"
            },
            {
                origin: "Norwich",
                destination: "London Liverpool Street",
                departureTime: "09:57",
                changes: 1,
                price: 25.00,
                cheapest: false,
                bookingUrl: "#"
            }
        ]

        return {
            reply: `Here are some options for your ${msg} journey:`,
            options: [], 
            tickets: exampleTickets   
        }
    }


        if (msg.includes("check delay") || msg === "check delay") {
            return {
                reply: "Please tell me the station you're currently at and how many minutes you're delayed.",
                options: []
            }
        }

        if (msg.includes("other")) {
            return {
                reply: "Please type your question and I'll do my best to help.",
                options: DEFAULT_OPTIONS.mainMenu
            }
        }

        return {
            reply: "I'm not sure I understood. You can choose an option below",
            options: DEFAULT_OPTIONS.mainMenu
        }
    }

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

        setMessages([
            ...newMessages, 
            { 
                text: data.reply, 
                sender: "bot",
                options: data.options || [],
                tickets: data.tickets || [] 
            }
        ])

    } catch (error) {
        console.log("Backend not connected, using hardcoded fallback")
        const fallback = getHardcodedReply(text)
        
        setMessages([
            ...newMessages, 
            { 
                text: fallback.reply, 
                sender: "bot",
                options: fallback.options || [],
                tickets: fallback.tickets || []   
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
                    TrainBot
                </div>

                <div className="chatMessages">
                    {messages.map((msg, i) => (
                        <Message key={i} text={msg.text} sender={msg.sender} options={msg.options || []} tickets={msg.tickets || []} onOptionClick={handleOptionClick} />
                    ))}
                    <div ref={bottomRef}></div>
                </div>

                <ChatInput sendMessage={sendMessage} />
            </div>

        </div>

)
}