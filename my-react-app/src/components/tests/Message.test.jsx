import { render, screen, fireEvent } from '@testing-library/react'
import Message from '../Message'

describe('Message', () => {
    test('displays trainbot message text correctly', () => {
        render(<Message text="Hello! How can I help?" sender="bot" />)
        expect(screen.getByText('Hello! How can I help?')).toBeInTheDocument()
    })

     test('displays user message text correctly', () => {
    render(<Message text="I need a ticket to London" sender="user" />)
    expect(screen.getByText('I need a ticket to London')).toBeInTheDocument()
  })

  test('renders ticket list when tickets prop is provided', () => {
    const tickets = [
      { origin: 'Norwich', destination: 'Colchester', price: 25.50, departureTime: '09:00' }
    ]
    
    render(
      <Message 
        text="Here are your tickets" 
        sender="bot" 
        tickets={tickets}
      />
    )
    
    expect(screen.getByText('Norwich')).toBeInTheDocument()
    expect(screen.getByText('Colchester')).toBeInTheDocument()
    expect(screen.getByText('£25.50')).toBeInTheDocument()
  })
})