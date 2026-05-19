import TicketList from "./TicketList"

export default function Message({ text, sender, options = [], onOptionClick, tickets = [], postMessage = "" }) {
    // Ensure text is a string
    const messageText = typeof text === 'string' ? text : String(text || '');
    
    return (
        <div className={`message ${sender}`}>
            <div className="messageText">     
                {messageText.split('\n').map((line, i) => (
                    <span key={i}>
                        {line}
                        {i < messageText.split('\n').length - 1 && <br />}
                    </span>
                ))}
            </div>
            {tickets.length > 0 && <TicketList tickets={tickets} />}
            {postMessage && (
                <div className="messageText">
                    {postMessage.split('\n').map((line, i) => (
                        <span key={i}>
                            {line}
                            {i < postMessage.split('\n').length - 1 && <br />}
                        </span>
                    ))}
                </div>
            )}
            {options.length > 0 && (
                <div className="messageOptions">
                    {options.map((opt, idx) => (
                        <button
                            key={idx}
                            className="optionBtn"
                            onClick={() => onOptionClick(opt)}
                        >
                            {opt}
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}