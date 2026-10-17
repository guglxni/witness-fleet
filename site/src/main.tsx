import { createRoot } from 'react-dom/client';
import { LaunchSite } from './LaunchSite';
import './style.css';
import './anatomy-styles.css';
const node=document.getElementById('root');if(!node)throw new Error('Missing #root mount node');createRoot(node).render(<LaunchSite/>);
