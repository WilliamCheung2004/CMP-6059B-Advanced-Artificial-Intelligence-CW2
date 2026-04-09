import "../styles/landing.css"

export default function LandingPage({ startChat }) {

    return (
        <div className="landing">
            <h1 className="title">TrainBot</h1>
                <div className="features">
                    <div className="feature">
                         <p>🚆</p>
                         <p>Cheapest Tickets</p>
                    </div>
                    <div className="feature">
                         <p>⏱</p>
                         <p>Delay Prediction</p>
                    </div>
                    <div className="feature">
                         <p>🔀</p>
                         <p>Contingency Plans</p>
                    </div>
                </div>
                <button className="startButton" onClick={startChat}>
                    Starting Chatting →
                </button>
            </div>
    )
}