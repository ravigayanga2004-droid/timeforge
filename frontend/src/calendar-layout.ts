import type {Assignment} from './api';
export function calendarLanes(sessions:Assignment[]){
 const output:Record<string,{lane:number;count:number}>={};
 for(let day=0;day<7;day++){
  const sorted=sessions.filter(a=>a.day===day).sort((a,b)=>a.start-b.start||a.end-b.end||a.section_id-b.section_id);
  let ends:number[]=[];let members:string[]=[];let clusterEnd=-1;
  const finish=()=>{for(const key of members)output[key].count=ends.length;ends=[];members=[]};
  for(const a of sorted){
   if(a.start>=clusterEnd)finish();
   clusterEnd=Math.max(clusterEnd,a.end);
   let lane=ends.findIndex(end=>end<=a.start);if(lane===-1)lane=ends.length;ends[lane]=a.end;
   const key=`${a.section_id}:${a.session_number}`;output[key]={lane,count:1};members.push(key);
  }
  finish();
 }
 return output;
}
