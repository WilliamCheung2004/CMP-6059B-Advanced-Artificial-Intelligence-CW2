import { render, screen } from '@testing-library/react'
import TicketCard from '../TicketCard'

describe('TicketCard', () => {
    test('displays origin, destination and price correctly', () => {
        const ticket = {
             origin: 'Norwich',
             destination: 'Colchester',
             departureTime: '09:00',
              price: 25.50
        }

        render(<TicketCard ticket={ticket} />)

        expect(screen.getByText('Norwich')).toBeInTheDocument()
                expect(screen.getByText('Colchester')).toBeInTheDocument()
        expect(screen.getByText(/25\.50/)).toBeInTheDocument()

    })

    test('shows "Cheapest" badge when cheapest = true', () => {
         const ticket = {
      origin: 'Norwich',
      destination: 'Colchester',
      departureTime: '09:00',
      price: 20.00,
      cheapest: true
    }

    render(<TicketCard ticket={ticket} />)

    expect(screen.getByText('Cheapest')).toBeInTheDocument()
    })

    test('shows booking link when bookingUrl is provided', () => {
         const ticket = {
      origin: 'Norwich',
      destination: 'Colchester',
      departureTime: '09:00',
      price: 25.00,
      bookingUrl: 'https://www.nationalrail.co.uk'
    }

    render(<TicketCard ticket={ticket} />)

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', 'https://www.nationalrail.co.uk')
    expect(link).toHaveAttribute('target', '_blank')
    })
})