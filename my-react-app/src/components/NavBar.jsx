import "../styles/navbar.css"
import { useState } from "react"

export default function Navbar({ goChat, onHelp }) {
    const [zoomLevel, setZoomLevel] = useState(0)
    const zoomSteps = [1.2, 1.4, 1.6, 1.8, 2.0, 2.2] 

    const handleZoomIn = () => {
        if (zoomLevel < zoomSteps.length - 1) {
            const newLevel = zoomLevel + 1
            setZoomLevel(newLevel)
            document.body.style.zoom = zoomSteps[newLevel]
        }
    }

    const handleZoomOut = () => {
        if (zoomLevel > 0) {
            const newLevel = zoomLevel - 1
            setZoomLevel(newLevel)
            document.body.style.zoom = zoomSteps[newLevel]
        }
    }

    return (
        <div className="navbar">
            <div className="navLeft">
                <span className="logoText">TrainBot</span>
            </div>

            <div className="navRight">
                <button className="zoomBtn" onClick={handleZoomIn} disabled={zoomLevel === zoomSteps.length - 1}>
                    Zoom In
                </button>
                <button className="zoomBtn" onClick={handleZoomOut} disabled={zoomLevel === 0}>
                    Zoom Out
                </button>
                <button className="chatBtn" onClick={goChat}>
                    Chat
                </button>
                <button className="helpBtn" onClick={onHelp}>
                    Help
                </button>
            </div>
        </div>
    )
}