import { useState } from "react"
import DatePicker from "react-datepicker"
import "react-datepicker/dist/react-datepicker.css"

export default function ChatInput({ sendMessage }) {
    const [text, setText] = useState("")
    const [showCalendar, setShowCalendar] = useState(false)
    const [selectedDate, setSelectedDate] = useState(null)
    const max_char = 300

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

    function handleDateChange(date) {
        setSelectedDate(date)
        setShowCalendar(false)

        const formattedDate = date.toLocaleDateString('en-GB', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
        })

        sendMessage(formattedDate)
    }

    const charLeft = max_char - text.length
    const isNearLimit = charLeft < 50

    return (
        <div className="chatInput">
            <button className="iconBtn" onClick={() => setShowCalendar(!showCalendar)} title="Select travel date(s)">
                📅
            </button>

            {showCalendar && (
                <div className="calendarWrapper">
                    <DatePicker selected={selectedDate} onChange={handleDateChange} inline minDate={new Date()} placeholderText="Select travel date"/>
                    </div>
            )}

            <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={handleKeyPress} placeholder="Type a message..." maxLength={max_char} />

            {text.length > 0 && (
                <span className={`charCounter ${isNearLimit ? 'warning' : ''}`}>{charLeft}</span>
            )}


            <button className="send" onClick={handleSend}>
                ↑
            </button>

        </div>
    )
}