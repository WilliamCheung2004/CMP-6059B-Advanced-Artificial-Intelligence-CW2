export default function Message({ text, sender}) {
    return (
        <div className={`message ${sender}`}>
            {text}
        </div>
    )
}