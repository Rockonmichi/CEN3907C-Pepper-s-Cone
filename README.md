# Pepper's Cone Holographic Display

## CEN3907C Computer Engineering Design 1
University of Florida  
Spring 2025  
Team: Michelle Garcia, Luna Khan, Chloe Sawatzki, Jennifer Senra Bruzon

This is an open source project for pepper's cone. A developemental "Hologram" for educational use.
here is our drive link: [https://drive.google.com/drive/folders/1SXS6x-iS6XAlsFAnU2rvifSmKICOc6r6?usp=drive_link](https://drive.google.com/drive/folders/1SXS6x-iS6XAlsFAnU2rvifSmKICOc6r6)
we took inspiration from: https://github.com/roxanneluo/Pepper-s-Cone-Unity to get started.

## Project Overview

This repository contains the pre-alpha build of our Pepper's Cone holographic display system. This innovative visualization tool creates 3D hologram-like images by displaying specially processed content on a horizontal screen with a cone-shaped reflector. Our project aims to scale this technology to a 72-inch display for educational environments, enabling remote instructors to appear as life-sized holographic presences in classrooms.

## Completed Work (Pre-Alpha)

### Environment Setup & Research
- Successfully set up development environment with GitHub and Unity Editor (older version for compatibility)
- Cloned and explored the original Pepper's Cone repository
- Conducted extensive research on Pepper's Ghost technology and optical illusions
- Reviewed multiple tutorials and academic papers on the technology
- Researched hardware requirements and compatibility issues

### Implementation Progress
- Successfully imported the GitHub repository into Unity and got the demo running
- Found and imported additional 3D models to use with the existing scene
- Created a small-scale phone demo using pre-processed video and clear sheets to demonstrate the concept
- Started preparing a bill of materials with alternative options for hardware components

### Meetings & Planning
- Regular meetings with stakeholder and team members to discuss progress
- Team discussions about the effects of Pepper's Ghost and how the Unity demonstration will integrate with hardware

## Project Architecture

Our pre-alpha build establishes the foundation for a three-component system:

### 1. Processing System
- Basic Unity environment for 3D model visualization
- Currently using pre-existing demo functionality from the reference repository
- Plans to develop custom processing for video input

### 2. User Interface
- Using Unity's built-in interface components
- Basic model selection and viewing capabilities
- Foundation for future expansion of control features

### 3. Display System
- Successfully tested concept with small-scale phone demonstration
- Exploring hardware options for tablet implementation
- Planning pathway to full-scale 72-inch display

## Known Limitations & Challenges

1. **Unity Version Compatibility**: The original project requires an older version of Unity, which caused initial setup challenges
   - *Resolution*: Successfully identified and installed the compatible version

2. **Hardware Integration**: Currently working on the software side, with hardware integration still in planning stages
   - *Next Steps*: Develop interface between Unity and physical display components

3. **3D Model Processing**: Currently using existing models, need to develop custom processing pipeline
   - *Progress*: Successfully imported and displayed additional models in the environment

4. **Scale Limitations**: Current demonstrations are small-scale only
   - *Plans*: Incremental scaling from phone demo to tablet to full-size implementation

## Setup & Usage

### System Requirements

- Unity (older version for compatibility - see notes in timesheet)
- GitHub for version control
- Compatible display device for testing

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/Rockonmichi/CEN3907C-Pepper-s-Cone.git
   ```

2. Open in Unity Editor (ensure correct version)

3. Load the demo scene to view current implementation

## Next Development Priorities

1. Complete tablet-scale implementation with physical cone
2. Develop more robust model/video selection interface
3. Start integrating video processing capabilities
4. Design and test calibration system for alignment
5. Research and plan for scaling to larger displays

## Team Contributions

The team has collectively invested time in:
- Research and exploration of the Pepper's Cone technology
- Setting up the development environment
- Running and testing the existing demo
- Creating small-scale proof-of-concept demonstrations
- Planning for hardware integration
- Exploring additional 3D models and content options

## Contact

For questions about this project, contact the team at:
- michelle.garcia@ufl.edu
- luna.khan@ufl.edu
- chloe.sawatzki@ufl.edu
- jennifer.senrabruzon@ufl.edu

## References

Key resources we've utilized:
1. Original Pepper's Cone GitHub repository: https://github.com/roxanneluo/Pepper-s-Cone-Unity
2. Academic paper: https://dl.acm.org/doi/10.1145/3126594.3126602
3. Research on Pepper's Ghost: https://www.researchgate.net/publication/368274915_Optical_Illusion_Some_Experiments_using_a_Pepper's_Ghost_Apparatus_with_Double_Chamber
4. Additional technical reference: https://www.mdpi.com/2673-4591/74/1/78

## License

This project is for educational purposes only.
