import React from 'react';

interface NodePopoverProps {
    onAction: (action: string) => void;
    onMouseEnter: () => void;
    onMouseLeave: () => void;
}

export const NodePopover: React.FC<NodePopoverProps> = ({ 
    onAction, 
    onMouseEnter, 
    onMouseLeave 
}) => {
    const actions = [
        { id: 'editInput', label: 'Edit input' },
        { id: 'editOutput', label: 'Edit output' },
        { id: 'changeLabel', label: 'Change label' },
        { id: 'seeInCode', label: 'See in code' }
    ];

    return (
        <div
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
            style={{
                position: 'absolute',
                top: '-45px',
                left: '50%',
                transform: 'translateX(-50%)',
                background: '#2c2c2c',
                border: '1px solid #444',
                borderRadius: '8px',
                padding: '8px',
                minWidth: '120px',
                zIndex: 1000,
                boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
            }}
        >
            {/* Speech bubble tail */}
            <div style={{
                position: 'absolute',
                bottom: '-6px',
                left: '50%',
                transform: 'translateX(-50%)',
                width: 0,
                height: 0,
                borderLeft: '6px solid transparent',
                borderRight: '6px solid transparent',
                borderTop: '6px solid #2c2c2c'
            }} />
            
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