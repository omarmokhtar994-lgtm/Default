/**
   @file sdb_validator.cc 
   @brief Validates a solution for an instance of the multi-skill shift design problem proposed in the paper *Modeling and solving a real-life multi-skill shift design problem* by Alex Bonutti, Sara Ceschia, Fabio De Cesco, Nysret Musliu and Andrea Schaerf, currently under revision. 

   This file contains all class and function definitions of the validator.
   It is compiled on Linux (with GNU C++) with the command:
      g++ -o sdb_validator sdb_validator.cc
   It is used with the command (e.g., on instance Toy.txt and solution Toy-sol.txt):
      ./sdb_validator Toy.txt Toy-sol.txt

   The input and output files are assumed to be correct. 
    
   @author Sara Ceschia (sara.ceschia@uniud.it),
           Andrea Schaerf (schaerf@uniud.it)

   @version 1.0
   @date 17 November 2014  
*/

#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <stdexcept>
#include <sstream>
#include <iomanip>

using namespace std;

// BEGIN OF HEADER

class ShiftType
{   
  friend class SDB_Input;
public:
  unsigned MinStart() const { return min_start; }
  unsigned MaxStart() const { return max_start; }
  unsigned MinLength() const { return min_length; }
  unsigned MaxLength() const { return max_length; }
  unsigned MaxStop() const { return max_stop; }
  bool DayAvailable(unsigned i) const { return day_availability.at(i); }  
  string ShortName() const { return short_name; }
  string Name() const { return name; }
  bool HasBreak() const { return has_break; }
  unsigned BreakLength() const { return break_length; }

  unsigned MinBreakStart() const { return min_break_start; }
  unsigned MaxBreakStart() const { return max_break_start; }
  unsigned MinBreakOffsetFromStart() const { return min_break_offset_from_start; }
  unsigned MinBreakOffsetFromEnd() const { return min_break_offset_from_end; }
  unsigned ShiftGranularity() const { return shift_granularity; }

  unsigned Skills() const { return skills; }
  unsigned Days() const { return days; }
  unsigned Granularity() const { return granularity; }
  unsigned TimeSlotsPerDay() const { return time_slots_per_day; }
private:
  unsigned days, granularity, time_slots_per_day, skills;
  unsigned min_start, max_start, min_length, max_length, max_stop;
  unsigned shift_granularity;
  vector<bool> day_availability;
  string name, short_name;
  bool has_break;
  unsigned break_length;
  unsigned min_break_start, max_break_start;
  unsigned min_break_offset_from_start, min_break_offset_from_end; 
};

class Shift
{
  friend ostream& operator<<(ostream &os, const Shift& s);
  friend bool operator==(const Shift& s1, const Shift& s2);
public:
  Shift() { break_position = 0; }
;
  Shift(const ShiftType *type);
  bool WorkTime(unsigned p) const; // check if p is included in the shift (considering also the break)
  bool CyclicWorkTime(unsigned p) const;  // check if p or p + TimeSlotsPerDay() is included in the shift
  bool InternalWorkTime(unsigned p) const  
  {if (!HasBreak()) return true;
    else return p < break_position || p >= break_position + BreakLength(); }
 // check if p is not a break time

  bool HasBreak() const { return type->HasBreak(); }
  unsigned BreakLength() const { return type->BreakLength(); }
  unsigned ActualLength() const { return HasBreak() ? length - BreakLength() : length; }

  unsigned Days() const { return type->Days(); }
  unsigned Skills() const { return type->Skills(); }
  unsigned Granularity() const { return type->Granularity(); }
  unsigned TimeSlotsPerDay() const { return type->TimeSlotsPerDay(); }

  unsigned start, length;
  vector<vector<unsigned> > number_of_workers; // per day, per skill
  vector<unsigned> number_of_workers_per_skill; // per skill
  string name;
  const ShiftType *type;
  // redundant data: if 0 then the shift is inactive
  unsigned total_workers;

  // break_position = -1 means NO BREAK
  unsigned break_position; // NOTE: if the shift goes around the clock, break position 
                           // becomes bigger that TimeSlotsPerDay() (it is not shifted with %)
};

/*************************************************************************** 
 * Input class
 ***************************************************************************/
class SDB_Input 
{
  friend ostream& operator<<(ostream&, const SDB_Input&);
public:
  SDB_Input(string id);
  unsigned Granularity() const { return granularity; }
  unsigned Days() const { return days; } 
  unsigned Skills() const { return skills; } 
  unsigned TimeSlots() const { return time_slots; } 
  unsigned TimeSlotsPerDay() const { return time_slots_per_day; }
  unsigned MinAvgShiftLength(unsigned sk) const { return min_avg_shift_length[sk]; }
  unsigned MaxAvgShiftLength(unsigned sk) const { return max_avg_shift_length[sk]; }
  const ShiftType& ShiftTypeVector(unsigned i) const 
      { return shift_type.at(i); }

  unsigned NumberOfShiftTypes() const { return shift_type.size(); }
  unsigned Requirements(unsigned t, unsigned sk) const
      { return requirements.at(t).at(sk); }
  unsigned TotalSkillRequirements(unsigned sk) const { return total_skill_requirements.at(sk); }
  unsigned TotalRequirements() const { return total_requirements; }
  unsigned ObjectiveWeight(unsigned i) const { return objective_weight.at(i); }
  void SetWeights(const vector<unsigned>& weight);
  bool Allocated() { return shift_type.size() > 0; }
  string InstanceId() const { return instance_id; }
  const ShiftType* FindShiftType(string type_name) const;

  bool HasShiftTypesWithMovingBreak() const { return has_shift_types_with_moving_break; }
  bool HasShiftTypesWithMovingStartLength() const { return has_shift_types_with_moving_start_length; }
  bool HasNightWork() const { return has_night_work; }

  void EnumerateShifts(ostream&, unsigned st) const; // print all shifts belonging to shift type of index st

private:
  unsigned total_requirements;
  unsigned granularity, days, time_slots, time_slots_per_day;
  vector<unsigned> min_avg_shift_length, max_avg_shift_length;
  string instance_id;
  unsigned skills;
  bool has_shift_types_with_moving_break, has_shift_types_with_moving_start_length, has_night_work;

  vector<ShiftType> shift_type;
  vector<unsigned> total_skill_requirements;
  vector<vector<unsigned> > requirements;
  vector<unsigned> objective_weight;
};

/***************************************************************************
 * Output class
 ***************************************************************************/
class SDB_Output 
{
  friend ostream& operator<<(ostream&, const SDB_Output&);
public:
  SDB_Output(const SDB_Input&, string file_name);
  void UpdateRedundantData();
  unsigned Shifts() const { return shift_vector.size(); }
  vector<Shift> shift_vector;
  const SDB_Input& in;
  vector<vector<int> > duty_difference;
  vector<unsigned> total_worked_shifts, total_worked_timeslots;
};

class SDB_Validator
{
public:
  SDB_Validator(const SDB_Input& i, const SDB_Output& o);
  void PrintCosts(std::ostream& os) const;
  void PrintTotalCost(std::ostream& os) const;
  
  const SDB_Input& in;  
  const SDB_Output& out; 
  unsigned SHIFT_NUMBER_COST;
  unsigned AVERAGE_SHIFT_LENGTH_COST;
  unsigned ComputeCostOnUnderStaffing() const;
  unsigned ComputeCostOnOverStaffing() const;
  unsigned ComputeCostOnAverageShiftLength() const;
  void PrintViolationsOnRequirements(ostream& os) const;
  void PrintViolationsOnAverageShiftLength(ostream& os) const;
};
// END OF HEADER


SDB_Input::SDB_Input(string instance_file) 
{ 
  string command, buffer, requirement_format;
  unsigned i, p , d, sk;
  unsigned shift_granularity_in_minutes, break_length_in_minutes;
  unsigned number_of_shift_types;
  unsigned min_length, max_length;
  char ch;

  ifstream is(instance_file.c_str());
  if (is.fail())
    throw runtime_error("Cannot open input file");
      
  string time_string1, time_string2;

  is >> buffer >> granularity;
  if ((24*60) % granularity != 0)
    throw runtime_error("Incompatible granularity");
  is >> buffer  >> days;
  is >> buffer  >> skills;

  time_slots_per_day = 24*60/granularity;
  time_slots = time_slots_per_day * days;

  min_avg_shift_length.resize(skills);
  max_avg_shift_length.resize(skills);

  vector<unsigned> min_duties(skills), max_duties(skills);

  is.ignore(256,':');
  for (sk = 0; sk < skills; sk++)
    is >> ch >> min_duties[sk] >> ch >> max_duties[sk] >> ch;
  double person_workload_in_hours;
  is.ignore(256,':');
  for (sk = 0; sk < skills; sk++)
     { 
       is  >> person_workload_in_hours;
       min_avg_shift_length[sk] = (person_workload_in_hours * 60 / max_duties[sk]) / granularity;
       max_avg_shift_length[sk] = (person_workload_in_hours * 60 / min_duties[sk]) / granularity;
     }
  is  >> buffer >> number_of_shift_types;
  shift_type.resize(number_of_shift_types);
  for (i = 0; i < number_of_shift_types; i++)
    {
      unsigned hours, minutes, j, min_offset_begin, min_offset_end;
      char ch; // used also to read the * (which means "in the following day")
      is >> shift_type[i].short_name 
	 >> shift_type[i].name;
      is >> hours >> ch >> minutes;
      shift_type[i].min_start = (hours*60 + minutes)/granularity;
      is >> hours >> ch >> minutes;
      shift_type[i].max_start = (hours*60 + minutes)/granularity;
      ch = is.get(); // read blank 
      ch = is.peek();
      if (ch == '*')
	{ // not used 
	  shift_type[i].max_stop = TimeSlotsPerDay() * 2; 
	  is.get();
	}
      else
	{
	  is >> hours >> ch >> minutes;
	  shift_type[i].max_stop = (hours*60 + minutes)/granularity;
	  ch = is.get();
	  if (ch == '*')
	    shift_type[i].max_stop += TimeSlotsPerDay();
	}
      is >> min_length >> max_length;
      shift_type[i].min_length = (min_length)/granularity;
      shift_type[i].max_length = (max_length)/granularity;

      if (shift_type[i].min_length < shift_type[i].max_length || shift_type[i].min_start < shift_type[i].max_start)
	{
	  has_shift_types_with_moving_start_length = true; // the type has the possibility of ES moves
	}
      if (shift_type[i].max_start + shift_type[i].max_length > TimeSlotsPerDay() && shift_type[i].max_stop > TimeSlotsPerDay())
        {
          has_night_work = true;
        }

      is >> shift_granularity_in_minutes;
      // shift_granularity must be multiples of granularity
      if (shift_granularity_in_minutes % granularity != 0)
	{
	  cerr << "Shift granularity: " << shift_granularity_in_minutes << ", granularity: " << granularity << endl;
	  throw runtime_error("Error in instance file");
	}
      shift_type[i].shift_granularity = shift_granularity_in_minutes/granularity;

      is >> ch;
      if (ch == 'B') // Shift type has a break
	{
	  
	  is >> buffer >> break_length_in_minutes >> time_string1 >> time_string2 
	     >> min_offset_begin >> min_offset_end;	  
	  shift_type[i].has_break = true;
	  if (break_length_in_minutes % granularity != 0)
            throw runtime_error("Break length incompatible with the granularity");
	  shift_type[i].break_length = break_length_in_minutes/granularity;
	  if (time_string1 == "*")
	    shift_type[i].min_break_start = shift_type[i].min_start; // not used
	  else
	    {
	      istringstream iss(time_string1);
	      iss >> hours >> ch >> minutes;
	      shift_type[i].min_break_start = (hours*60 + minutes)/granularity;
	    }
	  if (time_string2 == "*")
	    shift_type[i].max_break_start = shift_type[i].max_stop; // not used
	  else
	    {
	      istringstream iss(time_string2);
	      iss >> hours >> ch >> minutes;
	      shift_type[i].max_break_start = (hours*60 + minutes)/granularity;
	    }
	  shift_type[i].min_break_offset_from_start = min_offset_begin/granularity;
	  shift_type[i].min_break_offset_from_end = min_offset_end/granularity + shift_type[i].break_length;
	  if (shift_type[i].min_break_offset_from_start + shift_type[i].min_break_offset_from_end + shift_type[i].break_length < shift_type[i].max_length )
	    {
	      has_shift_types_with_moving_break = true; // the type has the possibility of moving the break
	    }
	}
      else
	{
	  is >> buffer;
	  shift_type[i].has_break = false;
	}


      shift_type[i].day_availability.resize(days);
      is >> ch;
      if (ch == '*')
	for (j = 0; j < days; j++)
	  shift_type[i].day_availability[j] = true;
      else
	{
	  for (j = 0; j < days; j++)
	    {
	      is >> ch;
	      if (ch == '1') shift_type[i].day_availability[j] = true;
	      else shift_type[i].day_availability[j] = false;
	    }
	  is >> ch;
	}
      shift_type[i].days = days;
      shift_type[i].skills = skills;
      shift_type[i].granularity = granularity;
      shift_type[i].time_slots_per_day = time_slots_per_day;
    }

  total_requirements = 0;
  total_skill_requirements.resize(skills,0);
  requirements.resize(time_slots,vector<unsigned>(skills,0));

  is  >> buffer >> requirement_format;

  if (requirement_format == "Compact")
    {
      unsigned start_hour, start_minute, end_hour, end_minute, start_period, end_period, workers, offset, i;
      char ch;
      while (is >> start_hour >> ch >> start_minute >> ch >> end_hour >> ch >> end_minute)
	{
	  start_period = (start_hour * 60 + start_minute) / granularity;
	  end_period = (end_hour * 60 + end_minute) / granularity;
	  for (d = 0; d < days; d++)
	    {
	      offset = time_slots_per_day * d;
	      for (sk = 0; sk < skills; sk++)
		{
		  is >> workers;
		  is.get(); //reads character '/' or blank
		  for (p = start_period; p < end_period; p++)
		    {
		      i = p + offset;
		      requirements[i][sk] = workers;
		      total_skill_requirements[sk] += workers;
		      total_requirements += workers;
		    }
		}
	    }
	}  
    }
  else
    throw runtime_error("Only compact format for requirements supported at present");
}

const ShiftType* SDB_Input::FindShiftType(string type_name) const
{
  for (unsigned t = 0; t < shift_type.size(); t++)
    if (shift_type[t].Name() == type_name)
      return &shift_type[t];
  return NULL;
}


SDB_Output::SDB_Output(const SDB_Input& p_in, string file_name)
  : in(p_in)
{ 
  unsigned d, sk, h, m, len;
  char ch;
  string s1, s2;
  string type_name;
  Shift sh;
  ifstream is(file_name.c_str());

  shift_vector.clear();  
  while (is >> sh.name >> ch >> type_name )
    { 
      sh.type = in.FindShiftType(type_name);
      if (sh.type == NULL)
        break;
      else
        is >> ch >> h >> ch >> m >> s1 >> len >> ch >> ch;
      sh.number_of_workers.resize(sh.type->Days(),vector<unsigned>(sh.type->Skills(),0));
      sh.number_of_workers_per_skill.resize(sh.type->Skills());
      for (sk = 0; sk < sh.Skills(); sk++)
        sh.number_of_workers_per_skill[sk] = 0;

      sh.start = (h * 60 + m) / sh.Granularity();
      sh.length = len / sh.Granularity();
      sh.total_workers = 0;
      
      if (ch == 'b') 
	{
	  is >> s1 >> s2 >> h >> ch >> m >> ch >> s1;
	  sh.break_position = (h * 60 + m) / sh.Granularity();
	  if (ch == '*')
            { // the break is in the following day
	      sh.break_position += sh.TimeSlotsPerDay();
	    }
	}
      else
	{
	  is >> s1 >> s2;
	  sh.break_position = 0;
	}
      for (d = 0; d < sh.Days(); d++)
	for (sk = 0; sk < sh.Skills(); sk++)
	  {
	    is  >> sh.number_of_workers[d][sk] >> ch;
	    sh.total_workers += sh.number_of_workers[d][sk];
	    sh.number_of_workers_per_skill[sk] += sh.number_of_workers[d][sk];
	  }
      is >> s1;
      shift_vector.push_back(sh);
    }
  UpdateRedundantData();
}

void SDB_Output::UpdateRedundantData()
{
  unsigned i, j, d, sk, day_start;

  duty_difference.resize(in.TimeSlots(),vector<int>(in.Skills()));
  total_worked_shifts.resize(in.Skills(),0);
  total_worked_timeslots.resize(in.Skills(),0);

  for (i = 0; i < in.TimeSlots(); i++)
    for (sk = 0; sk < in.Skills(); sk++)
      duty_difference[i][sk] = -in.Requirements(i,sk);

  for (j = 0; j < Shifts(); j++)
    if (shift_vector[j].total_workers > 0)
      {
	for (d = 0; d < in.Days(); d++)
	  {
	    day_start =  d* in.TimeSlotsPerDay();
	    for (i = shift_vector[j].start; 
		 i < shift_vector[j].start + shift_vector[j].length; i++)
	      if (shift_vector[j].InternalWorkTime(i))
		{		
		  for (sk = 0; sk < in.Skills(); sk++)
		    {
		      duty_difference[(i + day_start) % in.TimeSlots()][sk] +=
			shift_vector[j].number_of_workers[d][sk];
		    }      
		}
	  }
      }
  for (sk = 0; sk < in.Skills(); sk++)
    {  
      total_worked_shifts[sk] = 0;
      total_worked_timeslots[sk] = 0;
    }
  for (j = 0; j < Shifts(); j++)
    {
      if (shift_vector[j].total_workers > 0)
	for (d = 0; d < in.Days(); d++)
	  {
	    for (sk = 0; sk < in.Skills(); sk++)
	      {
		total_worked_shifts[sk] += shift_vector[j].number_of_workers[d][sk];
		if (shift_vector[j].HasBreak())
		  total_worked_timeslots[sk] += shift_vector[j].number_of_workers[d][sk] * 
		    (shift_vector[j].length - shift_vector[j].BreakLength());
		else
		  total_worked_timeslots[sk] += shift_vector[j].number_of_workers[d][sk] * 
		    shift_vector[j].length;
	      }
	  }
    }
}

int main(int argc, char* argv[])
{
  if (argc != 3)
    {
      std::cerr << "Usage:  " << argv[0] << " <input_file> <solution_file> " << std::endl;
      exit(1);
    }

  SDB_Input in(argv[1]);
  SDB_Output out(in, argv[2]);
  SDB_Validator validator(in, out);

  validator.PrintViolationsOnRequirements(cout);
  validator.PrintViolationsOnAverageShiftLength(cout);
  unsigned understaffing_violations = validator.ComputeCostOnUnderStaffing(),
    overstaffing_violations = validator.ComputeCostOnOverStaffing(),
    average_shift_length_violations = validator.ComputeCostOnAverageShiftLength();

  cout  << endl << "SUMMARY: " << endl;
  cout << "Violations on understaffing : " << in.Granularity() * understaffing_violations
       << " (" << understaffing_violations << " violations X " << in.Granularity() << " granularity)" << endl;
  cout << "Violations on overstaffing : " << in.Granularity() * overstaffing_violations
       << " (" << overstaffing_violations << " violations X " << in.Granularity() << " granularity)" << endl;
  cout << "Violations on shift number : " << out.Shifts() * validator.SHIFT_NUMBER_COST 
       << " (" << out.Shifts() << " violations X " << validator.SHIFT_NUMBER_COST << " weight)" << endl;
  cout << "Violations on average shift length : " << average_shift_length_violations * validator.AVERAGE_SHIFT_LENGTH_COST 
       << " (" << average_shift_length_violations << " violations X " << validator.AVERAGE_SHIFT_LENGTH_COST << " weight)" << endl;
  cout << endl;
  return 0;
} 

SDB_Validator::SDB_Validator(const SDB_Input& i, const SDB_Output& o)
  : in(i), out(o), SHIFT_NUMBER_COST(60), AVERAGE_SHIFT_LENGTH_COST(100)
{}

void SDB_Validator::PrintViolationsOnRequirements(ostream& os) const
{ 
  unsigned i, sk;
  for (i = 0; i < in.TimeSlots(); i++)
    for (sk = 0; sk < in.Skills(); sk++)
      if (out.duty_difference[i][sk] > 0)
	os << "Overstaffing by " <<  out.duty_difference[i][sk] << " at day " << (i / in.TimeSlotsPerDay())
           << " time " << (i%in.TimeSlotsPerDay()) * in.Granularity() / 60 << ":" 
           << setfill('0') << setw(2) << ((i%in.TimeSlotsPerDay()) * in.Granularity()) % 60 << " for skill " << sk << endl;
      else if (out.duty_difference[i][sk] < 0)
        os << "Understaffing by " <<  -out.duty_difference[i][sk] << " at day " << (i / in.TimeSlotsPerDay())
           << " time " << (i%in.TimeSlotsPerDay()) * in.Granularity() / 60 << ":" 
           << setfill('0') << setw(2) << ((i%in.TimeSlotsPerDay()) * in.Granularity()) % 60 << " for skill " << sk << endl;;
}

void SDB_Validator::PrintViolationsOnAverageShiftLength(ostream& os) const
{
  unsigned sk;
  unsigned min_working_timeslots, max_working_timeslots;

  for (sk = 0; sk < in.Skills(); sk++)
    {
      min_working_timeslots = in.MinAvgShiftLength(sk) * out.total_worked_shifts[sk];
      max_working_timeslots = in.MaxAvgShiftLength(sk) * out.total_worked_shifts[sk];
      
      if (out.total_worked_timeslots[sk] < min_working_timeslots)
	os << "Too few total working timeslots for skill " << sk << ": " <<  out.total_worked_timeslots[sk]
	   << ", min = " <<  min_working_timeslots << " (" << in.MinAvgShiftLength(sk) << " min_avg_length X " 
           << out.total_worked_shifts[sk] << " total worked shifts)" << endl;
      else if (out.total_worked_timeslots[sk] > max_working_timeslots)
	os << "Too many total working timeslots for skill " << sk << ": " <<  out.total_worked_timeslots[sk]
	   << ", max = " <<  max_working_timeslots << " (" << in.MaxAvgShiftLength(sk) << " max_avg_length X " 
           << out.total_worked_shifts[sk] << " total_worked_shifts)" << endl;
    }
}

unsigned SDB_Validator::ComputeCostOnUnderStaffing() const
{
  unsigned cost = 0;
  unsigned i, sk;
  for (i = 0; i < in.TimeSlots(); i++)
    for (sk = 0; sk < in.Skills(); sk++)
      if (out.duty_difference[i][sk] < 0)
	cost += -out.duty_difference[i][sk];
  return cost;

}

unsigned SDB_Validator::ComputeCostOnOverStaffing() const
{
  unsigned cost = 0;
  unsigned i, sk;
  for (i = 0; i < in.TimeSlots(); i++)
    for (sk = 0; sk < in.Skills(); sk++)
      if (out.duty_difference[i][sk] > 0)
	cost += out.duty_difference[i][sk];
  return cost;
}

unsigned SDB_Validator::ComputeCostOnAverageShiftLength() const
{  
  unsigned cost = 0;
  unsigned sk;
  unsigned min_working_timeslots, max_working_timeslots;

  for (sk = 0; sk < in.Skills(); sk++)
    {
      min_working_timeslots = in.MinAvgShiftLength(sk) * out.total_worked_shifts[sk];
      max_working_timeslots = in.MaxAvgShiftLength(sk) * out.total_worked_shifts[sk];
      
      if (out.total_worked_timeslots[sk] < min_working_timeslots)
	cost += min_working_timeslots - out.total_worked_timeslots[sk];
      else if (out.total_worked_timeslots[sk] > max_working_timeslots)
        cost += out.total_worked_timeslots[sk] - max_working_timeslots;
    }
  return cost;

}
