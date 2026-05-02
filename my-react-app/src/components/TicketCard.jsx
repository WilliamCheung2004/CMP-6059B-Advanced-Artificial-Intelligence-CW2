import "../styles/ticket.css"

export default function TickerCard({ ticket }) {
    const badge = ticket.cheapest ? "Cheapest" : ticket.fastest ? "Fastest" : null
    const isReturn = ticket.returnDepartureTime !== undefined

    return (
        <div className="ticketCard">
            <div className="ticketRoute">
                <span className="origin">{ticket.origin}</span>
                <span className="arrow">→</span>
                <span className="destination">{ticket.destination}</span>
            </div>

            <div className="ticketTime">
                <span className="departureTime">{isReturn ? "Out: " : ""}{ticket.departureTime}</span>
                {ticket.departureDate && (<span className="departureDate">{ticket.departureDate}</span>)}
                {ticket.changes !== undefined && (
                    <span className="changes">
                        {ticket.changes === 0 ? "Direct" : `${ticket.changes} change${ticket.changes > 1 ? "s" : ""}`}
                    </span>
                )}
            </div>

            {isReturn && (
                <div className="ticketTime">
                    <span className="departureTime">
                        Return: {ticket.returnDepartureTime}
                    </span>
                    {ticket.returnDepartureTime && (
                        <span className="departureDate">{ticket.returnDepartureDate}</span>
                    )}
                    {ticket.returnChanges !== undefined && (
                        <span className="changes">{ticket.returnChanges === 0 ? "Direct" : `${ticket.returnChanges} change${ticket.returnChanges > 1 ? "s" : ""}`}</span>
                    )}
                    </div>
            )}

            <div className="ticketFooter">
                <div className="price-wrapper">
                    <span className="price">£{ticket.price.toFixed(2)}</span>
                    {badge && <span className={`badge ${badge.toLowerCase()}`}>{badge}</span>}
                </div>
                <a
                    href={ticket.bookingUrl || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bookButton"
                >
                    Book →
                </a>
            </div>
        </div>
    )
}