import { render, screen } from '@testing-library/react'
import TicketList from '../TicketList'

describe('TicketList', () => {
    test('renders nothing when tickets array is empty', () => {
        const { container } = render(<TicketList tickets={[]} />)
        expect(container.firstChild).toBeNull()
    })

    test('renders nothing when tickets are null', () => {
        const { container } = render(<TicketList tickets={null} />)
        expect(container.firstChild).toBeNull()
    })

    test('renders multiple TicketCards when tickets provided', () => {
        const tickets = [
            { origin: 'Norwich', destination: 'Colchester', price: 10, departureTime: '09:00' },
      { origin: 'Cambridge', destination: 'Liverpool Street', price: 20, departureTime: '10:00' }
        ]

        render(<TicketList tickets={tickets} />)
    
    expect(screen.getByText('Norwich')).toBeInTheDocument()
    expect(screen.getByText('Cambridge')).toBeInTheDocument()
    })
})