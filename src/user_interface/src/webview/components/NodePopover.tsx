import React from 'react';
import { useIsVsCodeDarkTheme } from '../utils/themeUtils';

interface NodePopoverProps {
    onAction: (action: string) => void;
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    position?: 'above' | 'below';
}

export const NodePopover: React.FC<NodePopoverProps> = ({ 
    onAction, 
    onMouseEnter, 
    onMouseLeave,
    position = 'above',
}) => {
    const isDarkTheme = useIsVsCodeDarkTheme();
    const popoverBg = isDarkTheme ? '#4d4d4d' : '#ffffff';
    const popoverBorder = isDarkTheme ? '#6b6b6b' : '#cccccc';
    const arrowColor = popoverBg;

    const actions = [
        { id: 'editInput', label: 'Edit input' },
        { id: 'editOutput', label: 'Edit output' },
        { id: 'changeLabel', label: 'Change label' },
        { id: 'seeInCode', label: 'See in code' }
    ];

    const popoverStyle: React.CSSProperties = {
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        background: popoverBg,
        border: `1px solid ${popoverBorder}`,
        borderRadius: '8px',
        padding: '8px',
        minWidth: '120px',
        zIndex: 1000,
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        top: position === 'above' ? 'calc(-100% - 8px)' : position === 'below' ? 'calc(100% - 8px)' : undefined,
    };

    const arrowStyle: React.CSSProperties = position === 'above'
        ? {
              position: 'absolute',
              bottom: '-6px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '6px solid transparent',
              borderRight: '6px solid transparent',
              borderTop: `6px solid ${arrowColor}`,
          }
        : {
              position: 'absolute',
              top: '-6px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '6px solid transparent',
              borderRight: '6px solid transparent',
              borderBottom: `6px solid ${arrowColor}`,
          };

    return (
        <div
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
            style={popoverStyle}
        >
            {/* Speech bubble tail */}
            <div style={arrowStyle} />
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {actions.map(action => (
                    <button
                        key={action.id}
                        onClick={() => onAction(action.id)}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#fff',
                            padding: '4px 8px',
                            cursor: 'pointer',
                            textAlign: 'left',
                            borderRadius: '4px',
                            fontSize: '12px',
                            whiteSpace: 'nowrap'
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = '#444';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                        }}
                    >
                        {action.label}
                    </button>
                ))}
            </div>
        </div>
    );
};