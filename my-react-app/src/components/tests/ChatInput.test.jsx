import { render, screen, fireEvent } from '@testing-library/react'
import ChatInput from '../ChatInput'

describe('ChatInput', () => {
    test('calls sendMessage with input text when send button clicked', () => {
    const mockSend = vi.fn()
    render(<ChatInput sendMessage={mockSend} disabled={false} />)
    
    const input = screen.getByPlaceholderText('Type a message...')
    fireEvent.change(input, { target: { value: 'Hello bot' } })
    
    const sendButton = screen.getByText('↑')
    fireEvent.click(sendButton)
    
    expect(mockSend).toHaveBeenCalledWith('Hello bot')
  })

   test('calls sendMessage when Enter key is pressed', () => {
    const mockSend = vi.fn()
    render(<ChatInput sendMessage={mockSend} disabled={false} />)
    
    const input = screen.getByPlaceholderText('Type a message...')
    fireEvent.change(input, { target: { value: 'Test message' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    
    expect(mockSend).toHaveBeenCalledWith('Test message')
  })

   test('disables input when disabled prop is true (trainbot is typing)', () => {
    render(<ChatInput sendMessage={() => {}} disabled={true} />)
    
    const input = screen.getByPlaceholderText('Trainbot is typing...')
    expect(input).toBeDisabled()
  })
})