import {render,screen} from '@testing-library/react';
import {expect,it} from 'vitest';
import App from './App';
it('identifies the application',()=>{render(<App/>);expect(screen.getByRole('heading',{name:'TimeForge'})).toBeInTheDocument()});
