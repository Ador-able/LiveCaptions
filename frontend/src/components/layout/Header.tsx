import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Library, PlusCircle, Settings } from 'lucide-react';

export function Header() {
    const location = useLocation();

    const navItems = [
        { label: '任务列表', path: '/', icon: Library },
        { label: '新建任务', path: '/new', icon: PlusCircle },
    ];

    return (
        <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-14 items-center">
                <Link to="/" className="mr-6 flex items-center space-x-2">
                    <span className="hidden font-bold sm:inline-block text-xl tracking-tight text-primary">
                        LiveCaptions
                    </span>
                </Link>
                <nav className="flex items-center space-x-4 lg:space-x-6 text-sm font-medium">
                    {navItems.map((item) => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={cn(
                                "transition-colors hover:text-foreground/80 flex items-center space-x-2",
                                location.pathname === item.path ? "text-foreground" : "text-foreground/60"
                            )}
                        >
                            <item.icon className="h-4 w-4" />
                            <span>{item.label}</span>
                        </Link>
                    ))}
                </nav>
                <div className="ml-auto flex items-center space-x-2">
                    <Button variant="ghost" size="icon" aria-label="Settings">
                        <Settings className="h-4 w-4" />
                    </Button>
                </div>
            </div>
        </header>
    );
}
