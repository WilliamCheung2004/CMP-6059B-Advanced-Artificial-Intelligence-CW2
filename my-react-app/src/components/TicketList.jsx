import TicketCard from "./TicketCard"
import "../styles/ticket.css"

export default function TicketList({ tickets }) {
    if (!tickets || tickets.length === 0) return null

    return (
        <div className="ticketList">
            {tickets.map((ticket, idx) => (
                <TicketCard key={idx} ticket={ticket} />
            ))}
        </div>
    )
}