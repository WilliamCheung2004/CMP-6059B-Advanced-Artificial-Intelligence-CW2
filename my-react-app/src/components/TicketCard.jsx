import "../styles/ticket.css"

export default function TickerCard({ ticket }) {
    const badge = ticket.cheapest ? "Cheapest" : ticket.fastest ? "Fastest" : null

    return (
        <div className="ticketCard">
            <div className="ticketRoute">
                <span className="origin">{ticket.origin}</span>
                <span className="arrow">→</span>
                <span className="destination">{ticket.destination}</span>
            </div>

            <div className="ticketTime">
                <span className="departureTime">{ticket.departureTime}</span>
                {ticket.changes !== undefined && (
                    <span className="changes">
                        {ticket.changes === 0 ? "Direct" : `${ticket.changes} change${ticket.changes > 1 ? "s" : ""}`}
                    </span>
                )}
            </div>

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