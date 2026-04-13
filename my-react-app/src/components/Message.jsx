import TicketList from "./TicketList"

export default function Message({ text, sender, options = [], onOptionClick, tickets = [] }) {
    return (
        <div className={`message ${sender}`}>
            <div className="messageText">{text}</div>
            {tickets.length > 0 && <TicketList tickets={tickets} />}
            {options.length > 0 && (
                <div className="messageOptions">
                    {options.map((opt, idx) => (
                        <button key={idx} className="optionBtn" onClick={() => onOptionClick(opt)}
                        >
                            {opt}
                        </button>
                    ))}
                    </div>
            )}
            </div>


    )
}